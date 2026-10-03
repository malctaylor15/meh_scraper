export path1="$(dirname "$0")"
cd $path1
cd ..
echo "current working directory: "$PWD

DB_LOCATION="${MEH_DB_LOCATION:-/mnt/volume-nyc3-01/meh_data/meh_scraper.db}"

# Incremental backup: uploads only the monthly partitions that changed to
# s3://do-mt-backups/meh_db_incremental/ (see scripts/s3_sync.py).
source /home/malcolm/main/bin/activate
python scripts/s3_sync.py push --db "$DB_LOCATION"
sync_exit_status=$?
deactivate

# Optional full snapshot of the whole DB (old behavior, ~1.4GB upload).
if [ "$MEH_FULL_SNAPSHOT" = "1" ]
then
  export aws="/usr/local/bin/aws"
  DATE=`date +%m-%d-%y`
  new_file_name=meh_backup_${DATE}.db
  $aws s3 cp --no-progress "$DB_LOCATION" s3://do-mt-backups/meh_db_backups/${new_file_name}
fi

exit $sync_exit_status
