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