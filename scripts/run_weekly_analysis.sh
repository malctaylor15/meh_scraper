export path1="$(dirname "$0")"
# nordvpn connect
cd $path1
cd ..
echo "current working directory: "$PWD
DB_LOCATION="${MEH_DB_LOCATION:-/mnt/volume-nyc3-01/meh_data/meh_scraper.db}"
DATE=`date +%m-%d-%y`
FILENAME=Meh_Analysis_v1_${DATE}.ipynb
LOCATION=notebooks/run_notebooks/
FILEPATH=$LOCATION$FILENAME

echo $FILEPATH
source /home/malcolm/main/bin/activate
papermill notebooks/Meh_Analysis_v1.ipynb "$FILEPATH" -p db_location "$DB_LOCATION"
# When in QA use QA database
#papermill notebooks/Parse\ Meh\ API.ipynb $FILEPATH -p db_location data/meh_scraper_qa.db

export papermill_exit_status=$?
if [ $papermill_exit_status -eq 0 ]
then
  echo "removing "$FILEPATH
  rm $FILEPATH
fi

# nordvpn disconnect
deactivate
exit 0
