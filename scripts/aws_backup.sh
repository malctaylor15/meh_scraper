export path1="$(dirname "$0")"
cd $path1
cd ..
echo "current working directory: "$PWD

DATE=`date +%m-%d-%y`
new_file_name=meh_backup_${DATE}.db
/home/pi/.local/bin/aws s3 cp data/meh_scraper.db s3://scraper-backup/meh_db_backups/${new_file_name}
