export path1="$(dirname "$0")"
cd $path1
cd ..
echo "current working directory: "$PWD
export aws="/usr/local/bin/aws"

DATE=`date +%m-%d-%y`
new_file_name=meh_backup_${DATE}.db
$aws s3 cp data/meh_scraper.db s3://do-mt-backups/meh_db_backups/${new_file_name}
