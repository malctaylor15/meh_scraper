# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A cron-driven scraper for meh.com. There is no Python package, build step, linter, or test suite: all logic lives in Jupyter notebooks under `notebooks/`, and the shell scripts in `scripts/` run them headlessly with **papermill**. Everything writes to and reads from one SQLite database.

## Running

Each entrypoint `cd`s to the repo root, activates the virtualenv at `/home/malcolm/main/bin/activate`, runs papermill into `notebooks/run_notebooks/<Name>_<MM-DD-YY>.ipynb`, and deletes that output notebook if the run succeeds. A failed run leaves the executed notebook behind for debugging.

```bash
bash scripts/run_notebook.sh          # Parse Meh API.ipynb  -> raw_response_backup, products
bash scripts/run_site_scraper.sh      # Parse_Site.ipynb     -> raw_site_community_stats, selling_details
bash scripts/run_weekly_analysis.sh   # Meh_Analysis_v1.ipynb -> emails a summary (read-only on the DB)
bash scripts/aws_backup.sh            # incremental backup via scripts/s3_sync.py push
python scripts/s3_sync.py pull --out data/meh_restored.db   # rebuild a merged DB from the backup
```

Backups are monthly gzipped SQLite partitions plus a `manifest.json` in `s3://do-mt-backups/meh_db_incremental/`. Details and restore options are in `docs/database-location.md`. Use `--remote <local dir>` to test `push`/`pull` without touching S3.

**Database location:** the production DB is `/mnt/volume-nyc3-01/meh_data/meh_scraper.db` (see `docs/database-location.md`). Set `MEH_DB_LOCATION` to point any script at a different DB. Use this for QA so you don't write to production:

```bash
MEH_DB_LOCATION=data/meh_scraper_qa.db bash scripts/run_site_scraper.sh
```

To run a notebook directly: `papermill "notebooks/Parse Meh API.ipynb" out.ipynb -p db_location <path>`.

Setup is in `scripts/getting_started.sh` (venv + `scripts/requirements.txt`, which pins `pandas==0.25.3`). The base schema is in `scripts/create_db.sh` (it is SQL, not shell: `sqlite3 <db> < scripts/create_db.sh`). Example crontab lines are at the bottom of `getting_started.sh`.

## Architecture notes

- **Parameterization:** `Parse Meh API.ipynb`, `Parse_Site.ipynb`, and `Meh_Analysis_v1.ipynb` each have a cell tagged `parameters` that defines `db_location`. Papermill overrides it. Keep that tag and variable name if you edit those cells. The `db_location` default in each notebook, each shell script, and `docs/database-location.md` must stay in sync when the path changes.
- **Two data sources:**
  - *API* (`Parse Meh API.ipynb`): calls `api.meh.com/1/current.json`. It stores the raw JSON in `raw_response_backup`, flattens nested dicts into `parent_child` column names (lists are dropped), and appends the result to `products`. If the API returns new keys, the notebook rewrites the whole `products` table (`if_exists='replace'`) with the new columns added. Missing columns on the new row are filled with `None`.
  - *Site* (`Parse_Site.ipynb`): scrapes the `community-stats` block from meh.com with BeautifulSoup. It stores the raw HTML in `raw_site_community_stats` and appends the parsed metrics (page views, referrers, items/dollars sold) to `selling_details`. This runs several times a day, so there are many rows per date.
- **Analysis** (`Meh_Analysis_v1.ipynb`): takes roughly the last 2 weeks of `selling_details`, dedups it to one end-of-day row per date, joins `products` on `date`, builds HTML tables, and emails them.
- **External dependency:** the analysis and runner notebooks import `EmailSender` from `/home/malcolm/EmailSender1/` through `sys.path`. That code is not in this repo. `Run_Analysis_Notebooks.ipynb` and `Generalized Run Notebooks.ipynb` are alternative runners that run the analysis notebook and email you if it fails.
- Cells of type `raw` in the notebooks are disabled code (old experiments and QA DB copy commands). Papermill does not run them.
- `notebooks/run_notebooks/` and `data/` are gitignored, although some old run notebooks are already committed. The `.log` files at the repo root are cron output.
