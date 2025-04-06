#!/bin/bash

# --------------------------
# Load environment variables from .env file
# --------------------------

# Check if the .env file exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    exit 1
fi

# Load variables
export $(grep -v '^#' .env | xargs)

sudo apt-get update
sudo apt-get install -y mariadb-client-10.5

mysql -h db-sandbox -u root -p$MYSQL_ROOT_PASSWORD -e "CREATE DATABASE IF NOT EXISTS sandbox;"

curl -X 'GET' \
  'icdapi/icd/entity' \
  -H 'accept: application/json' \
  -H 'API-Version: v2' \
  -H 'Accept-Language: en'

# --------------------------
# Install JupyterLab
# --------------------------

echo "🚀 Installing Jupyter Notebook..."
pip install notebook

# Seeding ICD-10 to 11 cross reference mapping tables
# ------------------------------------------------

cd icd11_mapping_tool
wget https://icdcdn.who.int/static/releasefiles/2025-01/mapping.zip
unzip mapping.zip -d mapping
sudo chmod +x seed_icd_cross_reference_tables.sh
./seed_icd_cross_reference_tables.sh -u root -proot -d sandbox -h db-sandbox