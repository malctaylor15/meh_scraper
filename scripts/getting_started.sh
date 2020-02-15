
# Create python virtual environment
python3 -m venv meh_scraper_env
source meh_scraper_env/bin/activate
pip install -r scripts/requirements.txt
mkdir notebooks/run_notebooks
mkdir data
sqlite3 data/meh_scraper.db < create_db.sh

# Optional -- create SQLite3 Databases
# bash create_db.sh

# Get an API Key from meh.com
# https://meh.com/developers-developers-developers

# Run the notebook using papermill
bash scripts/run_notebook.sh
58 23 * * * bash /home/pi/meh_scraper/scripts/run_notebook.sh
53 */3 * * * bash /home/pi/meh_scraper/scripts/run_site_scraper.sh

