"""Incremental backup of the meh scraper SQLite DB to S3, and restore/merge back.

Every table is split into monthly partitions (by its `date` column). Each
partition is a small gzipped SQLite file holding just that month's rows, with
the table's original schema, so types and NULLs round-trip exactly.

    <remote>/manifest.json
    <remote>/<table>/<table>_<YYYY-MM>.db.gz

push: scans only months >= the newest month already in the manifest (or all
      months with --full) and uploads the partitions whose content changed.
pull: downloads partitions (optionally filtered by table/month range) and
      merges them into one SQLite DB with the same schema as production.

Examples:
    python scripts/s3_sync.py push
    python scripts/s3_sync.py status
    python scripts/s3_sync.py pull --out data/meh_restored.db
    python scripts/s3_sync.py pull --out data/recent.db --tables products selling_details --since 2026-01

--remote accepts s3://bucket/prefix or a local directory (handy for testing).
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile

DEFAULT_DB = os.environ.get('MEH_DB_LOCATION', '/mnt/volume-nyc3-01/meh_data/meh_scraper.db')
DEFAULT_REMOTE = os.environ.get('MEH_SYNC_REMOTE', 's3://do-mt-backups/meh_db_incremental')
MANIFEST_KEY = 'manifest.json'
BATCH_SIZE = 500


# ---------------------------------------------------------------- storage

class LocalStore:
    def __init__(self, root):
        self.root = root

    def _path(self, key):
        return os.path.join(self.root, key)

    def get_bytes(self, key):
        try:
            with open(self._path(key), 'rb') as hnd:
                return hnd.read()
        except FileNotFoundError:
            return None

    def put_bytes(self, key, data):
        os.makedirs(os.path.dirname(self._path(key)) or self.root, exist_ok=True)
        with open(self._path(key), 'wb') as hnd:
            hnd.write(data)

    def put_file(self, key, path):
        os.makedirs(os.path.dirname(self._path(key)), exist_ok=True)
        shutil.copyfile(path, self._path(key))

    def get_file(self, key, path):
        shutil.copyfile(self._path(key), path)


class S3Store:
    def __init__(self, url):
        import boto3
        bucket, _, prefix = url[len('s3://'):].partition('/')
        self.bucket = bucket
        self.prefix = prefix.strip('/')
        self.s3 = boto3.client('s3')

    def _key(self, key):
        return f'{self.prefix}/{key}' if self.prefix else key

    def get_bytes(self, key):
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=self._key(key))['Body'].read()
        except self.s3.exceptions.NoSuchKey:
            return None

    def put_bytes(self, key, data):
        self.s3.put_object(Bucket=self.bucket, Key=self._key(key), Body=data)

    def put_file(self, key, path):
        self.s3.upload_file(path, self.bucket, self._key(key))

    def get_file(self, key, path):
        self.s3.download_file(self.bucket, self._key(key), path)


def open_store(remote):
    return S3Store(remote) if remote.startswith('s3://') else LocalStore(remote)


def load_manifest(store):
    raw = store.get_bytes(MANIFEST_KEY)
    if raw is None:
        return {'version': 1, 'tables': {}}
    return json.loads(raw)


# ---------------------------------------------------------------- helpers

def quote(name):
    return '"' + name.replace('"', '""') + '"'


def now_str():
    return datetime.datetime.now().isoformat(timespec='seconds')


def table_columns(con, table, schema='main'):
    return [r[1] for r in con.execute(f'PRAGMA {schema}.table_info({quote(table)})')]


def partition_key(table, month):
    return f'{table}/{table}_{month}.db.gz'


def gzip_file(src, dst):
    with open(src, 'rb') as fin, gzip.open(dst, 'wb', compresslevel=6) as fout:
        shutil.copyfileobj(fin, fout, 1024 * 1024)


def gunzip_file(src, dst):
    with gzip.open(src, 'rb') as fin, open(dst, 'wb') as fout:
        shutil.copyfileobj(fin, fout, 1024 * 1024)


# ---------------------------------------------------------------- push

class Partition:
    """One month of one table, written to a standalone SQLite file."""

    def __init__(self, path, table, ddl, columns):
        self.path = path
        self.con = sqlite3.connect(path)
        self.con.execute(ddl)
        self.insert_sql = 'INSERT INTO {} ({}) VALUES ({})'.format(
            quote(table), ', '.join(quote(c) for c in columns), ', '.join('?' * len(columns)))
        self.rows = 0
        self.hash = hashlib.sha256()
        self.pending = []

    def add(self, row):
        self.rows += 1
        self.hash.update(repr(row).encode())
        self.pending.append(row)
        if len(self.pending) >= BATCH_SIZE:
            self.flush()

    def flush(self):
        self.con.executemany(self.insert_sql, self.pending)
        self.pending = []

    def close(self):
        self.flush()
        self.con.commit()
        self.con.close()


def build_partitions(src, table, since_month, workdir):
    ddl = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
    columns = table_columns(src, table)
    date_idx = columns.index('date')

    sql = f'SELECT * FROM {quote(table)}'
    params = ()
    if since_month:
        sql += ' WHERE date >= ?'
        params = (since_month,)
    sql += ' ORDER BY rowid'

    parts = {}
    for row in src.execute(sql, params):
        month = row[date_idx][:7]
        if month not in parts:
            path = os.path.join(workdir, f'{table}_{month}.db')
            parts[month] = Partition(path, table, ddl, columns)
        parts[month].add(row)
    for part in parts.values():
        part.close()
    return ddl, columns, parts


def push(args):
    store = open_store(args.remote)
    manifest = load_manifest(store)
    src = sqlite3.connect(f'file:{args.db}?mode=ro', uri=True, timeout=60)
    tables = [r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    total_uploaded = 0
    for table in tables:
        if 'date' not in table_columns(src, table):
            print(f'[{table}] no date column, skipping')
            continue
        remote_tbl = manifest['tables'].get(table, {'partitions': {}})
        remote_parts = remote_tbl['partitions']
        since = None if args.full or not remote_parts else max(remote_parts)

        workdir = tempfile.mkdtemp(prefix=f'meh_sync_{table}_', dir=args.workdir)
        try:
            ddl, columns, parts = build_partitions(src, table, since, workdir)

            # Refuse to replace a month with fewer rows than the backup already holds:
            # that means the local DB is missing data and the backup is the better copy.
            scanned_months = [m for m in remote_parts if since is None or m >= since]
            shrunk = [(m, parts[m].rows if m in parts else 0, remote_parts[m]['rows']) for m in scanned_months
                      if (parts[m].rows if m in parts else 0) < remote_parts[m]['rows']]
            if shrunk and not args.force:
                for m, local_rows, remote_rows in shrunk:
                    print(f'[{table}] {m}: local has {local_rows} rows, backup has {remote_rows}', file=sys.stderr)
                sys.exit(f'[{table}] refusing to overwrite larger backup partitions (use --force to override)')

            changed = sorted(m for m, p in parts.items()
                             if remote_parts.get(m, {}).get('sha256') != p.hash.hexdigest())
            print(f'[{table}] scanned {len(parts)} month(s) since {since or "the beginning"}, '
                  f'{len(changed)} changed')

            for month in changed:
                part = parts[month]
                key = partition_key(table, month)
                if args.dry_run:
                    print(f'  would upload {key} ({part.rows} rows)')
                    continue
                gz_path = part.path + '.gz'
                gzip_file(part.path, gz_path)
                os.remove(part.path)
                size = os.path.getsize(gz_path)
                store.put_file(key, gz_path)
                os.remove(gz_path)
                remote_parts[month] = {
                    'key': key,
                    'rows': part.rows,
                    'sha256': part.hash.hexdigest(),
                    'bytes': size,
                    'pushed_at': now_str(),
                }
                total_uploaded += size
                print(f'  uploaded {key}: {part.rows} rows, {size / 1048576:.1f} MiB')

            remote_tbl.update({'ddl': ddl, 'columns': columns, 'partitions': remote_parts})
            manifest['tables'][table] = remote_tbl
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
    src.close()

    if args.dry_run:
        print('dry run: nothing uploaded')
        return
    manifest['updated_at'] = now_str()
    store.put_bytes(MANIFEST_KEY, json.dumps(manifest, indent=1, sort_keys=True).encode())
    print(f'done: uploaded {total_uploaded / 1048576:.1f} MiB, manifest updated')


# ---------------------------------------------------------------- pull

def pull(args):
    store = open_store(args.remote)
    manifest = load_manifest(store)
    if not manifest['tables']:
        sys.exit(f'no manifest found at {args.remote}')
    if os.path.exists(args.out):
        if not args.overwrite:
            sys.exit(f'{args.out} already exists (use --overwrite to replace it)')
        os.remove(args.out)

    tables = args.tables or sorted(manifest['tables'])
    unknown = set(tables) - set(manifest['tables'])
    if unknown:
        sys.exit(f'unknown table(s): {", ".join(sorted(unknown))}')

    out = sqlite3.connect(args.out)
    workdir = tempfile.mkdtemp(prefix='meh_pull_', dir=args.workdir)
    try:
        for table in tables:
            info = manifest['tables'][table]
            # The manifest keeps the newest schema, so columns added later (products grows
            # when the API adds fields) exist in the merged table; older months get NULLs.
            out.execute(info['ddl'])
            target_cols = set(table_columns(out, table))
            months = sorted(m for m in info['partitions']
                            if (not args.since or m >= args.since) and (not args.until or m <= args.until))
            rows = 0
            for month in months:
                gz_path = os.path.join(workdir, f'{table}_{month}.db.gz')
                db_path = gz_path[:-3]
                store.get_file(info['partitions'][month]['key'], gz_path)
                gunzip_file(gz_path, db_path)
                os.remove(gz_path)

                out.execute('ATTACH DATABASE ? AS part', (db_path,))
                cols = ', '.join(quote(c) for c in table_columns(out, table, 'part') if c in target_cols)
                cur = out.execute(f'INSERT INTO main.{quote(table)} ({cols}) SELECT {cols} FROM part.{quote(table)}')
                rows += cur.rowcount
                out.commit()
                out.execute('DETACH DATABASE part')
                os.remove(db_path)
            print(f'[{table}] merged {len(months)} month(s), {rows} rows')
    finally:
        out.close()
        shutil.rmtree(workdir, ignore_errors=True)
    print(f'wrote {args.out}')


# ---------------------------------------------------------------- status

def status(args):
    manifest = load_manifest(open_store(args.remote))
    if not manifest['tables']:
        print(f'no manifest at {args.remote}')
        return
    print(f'{args.remote} (updated {manifest.get("updated_at")})')
    for table, info in sorted(manifest['tables'].items()):
        parts = info['partitions']
        rows = sum(p['rows'] for p in parts.values())
        size = sum(p['bytes'] for p in parts.values()) / 1048576
        last = max(parts) if parts else None
        last_push = parts[last]['pushed_at'] if last else None
        print(f'  {table:28s} {len(parts):4d} months  {rows:8d} rows  {size:8.1f} MiB  '
              f'{min(parts) if parts else "-"} .. {last or "-"}  (last pushed {last_push})')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--remote', default=DEFAULT_REMOTE, help='s3://bucket/prefix or local directory')
    parser.add_argument('--workdir', default=None, help='scratch directory for partition files')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('push', help='upload new/changed monthly partitions')
    p.add_argument('--db', default=DEFAULT_DB)
    p.add_argument('--full', action='store_true', help='rescan every month, not just the latest')
    p.add_argument('--force', action='store_true', help='allow overwriting partitions that have more rows')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=push)

    p = sub.add_parser('pull', help='download partitions and merge into one SQLite DB')
    p.add_argument('--out', required=True)
    p.add_argument('--tables', nargs='+')
    p.add_argument('--since', help='first month to include, YYYY-MM')
    p.add_argument('--until', help='last month to include, YYYY-MM')
    p.add_argument('--overwrite', action='store_true')
    p.set_defaults(func=pull)

    p = sub.add_parser('status', help='summarize what is in the backup')
    p.set_defaults(func=status)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
