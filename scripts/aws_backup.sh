export path1="$(dirname "$0")"
cd $path1
cd ..
echo "current working directory: "$PWD
export aws="/usr/local/bin/aws"

DB_LOCATION="${MEH_DB_LOCATION:-/mnt/volume-nyc3-01/meh_data/meh_scraper.db}"
DATE=`date +%m-%d-%y`
new_file_name=meh_backup_${DATE}.db
$aws s3 cp "$DB_LOCATION" s3://do-mt-backups/meh_db_backups/${new_file_name}
