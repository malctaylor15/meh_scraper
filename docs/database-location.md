# Meh scraper database location

The production SQLite database for the scraper pipeline now lives on the mounted volume at:

```text
/mnt/volume-nyc3-01/meh_data/meh_scraper.db
```

This replaces the previous production database path:

```text
/home/malcolm/meh_scraper/data/meh_scraper.db
```

## Pipeline behavior

- API scraping writes to the mounted-volume database through `scripts/run_notebook.sh`, which passes the path into `notebooks/Parse Meh API.ipynb` as the `db_location` papermill parameter.
- Site scraping writes to the same mounted-volume database through `scripts/run_site_scraper.sh`, which passes the path into `notebooks/Parse_Site.ipynb` as the `db_location` papermill parameter.
- Weekly analysis reads from the same mounted-volume database through `scripts/run_weekly_analysis.sh`, which passes the path into `notebooks/Meh_Analysis_v1.ipynb` as the `db_location` papermill parameter.
- Backup jobs now upload the mounted-volume database through `scripts/aws_backup.sh`.
- New setup initializes the mounted-volume database directory and schema through `scripts/getting_started.sh` and `scripts/create_db.sh`.

The shell entrypoints default to `/mnt/volume-nyc3-01/meh_data/meh_scraper.db` and can be temporarily pointed elsewhere by setting `MEH_DB_LOCATION` before running a script, for example:

```bash
MEH_DB_LOCATION=/tmp/meh_scraper_qa.db bash scripts/run_notebook.sh
```

## Files affected

| File | Change |
| --- | --- |
| `scripts/run_notebook.sh` | API scrape entrypoint now defaults to the mounted-volume database and passes it to papermill. |
| `scripts/run_site_scraper.sh` | Site scrape entrypoint now defaults to the mounted-volume database and passes it to papermill. |
| `scripts/run_weekly_analysis.sh` | Weekly analysis entrypoint now defaults to the mounted-volume database and passes it to papermill. |
| `scripts/aws_backup.sh` | Backup uploads the mounted-volume database by default. |
| `scripts/getting_started.sh` | Setup creates `/mnt/volume-nyc3-01/meh_data` and initializes the database there. |
| `scripts/create_db.sh` | Schema creation comment documents the mounted-volume database path. |
| `notebooks/Parse Meh API.ipynb` | Default `db_location` parameter now points at the mounted-volume database. |
| `notebooks/Parse_Site.ipynb` | Default `db_location` parameter now points at the mounted-volume database. |
| `notebooks/Meh_Analysis_v1.ipynb` | Default `db_location` parameter now points at the mounted-volume database. |
| `notebooks/Run_Analysis_Notebooks.ipynb` | Analysis runner uses the mounted-volume database when invoking analysis notebooks. |
| `notebooks/Backfill Products Table, dedup backup.ipynb` | QA copy source updated to use the mounted-volume database as production input. |
| `notebooks/run_notebooks/*.ipynb` | Checked-in historical papermill run notebooks updated so their recorded `db_location` values and QA copy examples no longer reference the old local database path. |

## Backups (incremental)

`scripts/aws_backup.sh` (cron, `meh-backup` job) runs `scripts/s3_sync.py push`, which uploads to `s3://do-mt-backups/meh_db_incremental/`:

```text
manifest.json                              # per table: schema, and per month: rows, sha256, size
<table>/<table>_<YYYY-MM>.db.gz            # gzipped SQLite file holding that month's rows
```

- Each push rescans only the newest month already in the manifest and any later months, and uploads only partitions whose content hash changed. `--full` rescans every month.
- A push refuses to replace a partition with one that has fewer rows (protects the backup from a truncated or restored local DB). Override with `--force`.
- The full history is ~53 MiB compressed versus ~1.4 GiB for a raw copy. Set `MEH_FULL_SNAPSHOT=1` to also upload a full copy to `meh_db_backups/` as before.
- The push holds a read lock on the DB while scanning (~30s). Schedule it away from the :15/:45 site-scraper runs.

Restore or build a merged view:

```bash
python scripts/s3_sync.py status
python scripts/s3_sync.py pull --out data/meh_restored.db                     # everything
python scripts/s3_sync.py pull --out data/recent.db --tables products selling_details --since 2026-01
MEH_DB_LOCATION=data/recent.db bash scripts/run_weekly_analysis.sh
```

`pull` creates each table from the latest schema in the manifest, so months saved before `products` gained a column come back with NULLs in that column. `--remote <dir>` points either command at a local directory instead of S3 for testing.
