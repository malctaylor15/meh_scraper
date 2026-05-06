export path1="$(dirname "$0")"
cd $path1
cd ..
echo "current working directory: "$PWD
DB_LOCATION="${MEH_DB_LOCATION:-/mnt/volume-nyc3-01/meh_data/meh_scraper.db}"
DATE=`date +%m-%d-%y`
FILENAME=Parse_Meh_API_${DATE}.ipynb
LOCATION=notebooks/run_notebooks/
FILEPATH=$LOCATION$FILENAME

echo $FILEPATH
source /home/malcolm/main/bin/activate
papermill notebooks/Parse\ Meh\ API.ipynb "$FILEPATH" -p db_location "$DB_LOCATION"
# When in QA use QA database
#papermill notebooks/Parse\ Meh\ API.ipynb $FILEPATH -p db_location data/meh_scraper_qa.db

export papermill_exit_status=$?
if [ $papermill_exit_status -eq 0 ]
then
  echo "removing "$FILEPATH
  rm $FILEPATH
fi

deactivate
exit 0

# bash /home/malcolm/meh_scraper/scripts/run_notebook.sh > /home/malcolm/meh_scraper/run_notebook.log