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
