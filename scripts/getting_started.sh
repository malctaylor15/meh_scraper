
# Create python virtual environment
python3 -m venv meh_scraper_env
source meh_scraper_env/bin/activate
pip install -r scripts/requirements.txt


# Optional -- create SQLite3 Databases
# bash create_db.sh

# Get an API Key from meh.com
# https://meh.com/developers-developers-developers

# Run the notebook using papermill
bash scripts/run_notebook.sh
