#!/bin/bash

# Variables
MYSQL_PORT=3306

while getopts ":u:p:d:h:P:" opt; do
  case ${opt} in
    u ) MYSQL_USER=$OPTARG ;;
    p ) MYSQL_PASS=$OPTARG ;;
    d ) MYSQL_DB=$OPTARG ;;
    h ) MYSQL_HOST=$OPTARG ;;
    P ) MYSQL_PORT=$OPTARG ;;
    \? )
      echo "❌ ERROR: Invalid option: -$OPTARG"
      exit 1
      ;;
    : )
      echo "❌ ERROR: Option -$OPTARG requires an argument."
      exit 1
      ;;
  esac
done

shift $((OPTIND -1))

# Validate parameters
if [ -z "$MYSQL_USER" ] || [ -z "$MYSQL_PASS" ] || [ -z "$MYSQL_DB" ] || [ -z "$MYSQL_HOST" ]; then
    echo "❌ ERROR: Missing required parameters."
    exit 1
fi

# Directories
INPUT_DIR="./mapping"

# File-to-table mapping
declare -A TABLES=(
    ["10To11MapToMultipleCategories.txt"]="icd11_10To11MapToMultipleCategories"
    ["10To11MapToOneCategory.txt"]="icd11_10To11MapToOneCategory"
    ["11To10MapToOneCategory.txt"]="icd11_11To10MapToOneCategory"
    ["foundation_10To11MapToOneCategory.txt"]="icd11_foundation_10To11MapToOneCategory"
    ["foundation_11To10MapToOneCategory.txt"]="icd11_foundation_11To10MapToOneCategory"
)

# Step: Import each file into its corresponding table
for file in "${!TABLES[@]}"; do
    table="${TABLES[$file]}"
    full_path="$INPUT_DIR/$file"

    if [ -f "$full_path" ]; then
        mysql --local-infile=1 -u"$MYSQL_USER" -p"$MYSQL_PASS" -h "$MYSQL_HOST" -P "$MYSQL_PORT" -e "
            USE $MYSQL_DB;
            LOAD DATA LOCAL INFILE '$full_path'
            INTO TABLE $table
            FIELDS TERMINATED BY '\t'
            LINES TERMINATED BY '\n'
            IGNORE 1 ROWS;
        "
    else
        echo "⚠️ WARNING: File not found: $full_path"
    fi
done