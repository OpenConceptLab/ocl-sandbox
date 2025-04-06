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

# --------------------------
# Install JupyterLab
# --------------------------

echo "🚀 Installing Jupyter Notebook..."
pip install notebook

# Start Jupyter Notebook in the background
echo "🚀 Starting Jupyter Notebook..."
jupyter notebook --ip=0.0.0.0 --allow-root --NotebookApp.token="${JUPYTER_NB_TOKEN}" --NotebookApp.password='' --NotebookApp.port=8888 &

# --------------------------
# Install MySQL
# --------------------------

echo "🔧 Installing MySQL Client and Server..."
sudo apt-get update
DEBIAN_FRONTEND=noninteractive sudo apt-get install -y mysql-client mysql-server

# Start MySQL manually
echo "🛢️ Starting MySQL server manually..."
mysqld_safe --skip-networking=0 --bind-address=0.0.0.0 &

# Wait a few seconds to ensure MySQL is ready
sleep 10

# Create the database if it doesn't exist
echo "🛢️ Creating database if not exists..."
mysql -uroot -e "CREATE DATABASE IF NOT EXISTS analytics;"

# --------------------------
# Final messages
# --------------------------

echo "✅ Environment setup completed!"
echo ""
echo "🌐 Jupyter running at: http://localhost:8888"
echo "🛢️ MySQL service running (user: root, no password by default)"