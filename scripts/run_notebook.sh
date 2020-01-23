export path1="$(dirname "$0")"
cd $path1
cd ..
echo "current working directory: "$PWD
DATE=`date +%d-%m-%y`
FILENAME=Parse\ Meh\ API_${DATE}.ipynb
LOCATION=notebooks/run_notebooks/
FILEPATH=$LOCATION$FILENAME

echo $FILEPATH
source meh_scraper_env/bin/activate
papermill notebooks/Parse\ Meh\ API.ipynb $FILEPATH -p db_location data/meh_scraper.db
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