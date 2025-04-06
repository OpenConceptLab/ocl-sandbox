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

mysql -uroot -p"$MYSQL_PASS" -h "$MYSQL_HOST" -P "$MYSQL_PORT" $MYSQL_DB <<'SQL'
CREATE TABLE IF NOT EXISTS icd11_10To11MapToMultipleCategories (
    `10ClassKind` VARCHAR(16),
    `Depth` VARCHAR(1),
    `icd10Code` VARCHAR(7),
    `icd10Chapter` VARCHAR(5),
    `icd10Title` VARCHAR(186),
    `11ClassKind` VARCHAR(10),
    `Depth_11` VARCHAR(1),
    `ICD_11_Foundation_URI` VARCHAR(39),
    `Linearization_release_URI` VARCHAR(67),
    `icd11Code` VARCHAR(28),
    `icd11Chapter` VARCHAR(122),
    `icd11Title` VARCHAR(403)
);

CREATE TABLE IF NOT EXISTS icd11_10To11MapToOneCategory (
    `10ClassKind` VARCHAR(16),
    `10DepthInKind` VARCHAR(1),
    `icd10Code` VARCHAR(7),
    `icd10Chapter` VARCHAR(5),
    `icd10Title` VARCHAR(186),
    `11ClassKind` VARCHAR(10),
    `11DepthInKind` VARCHAR(1),
    `ICD_11_FoundationURI` VARCHAR(39),
    `Linearization_releaseURI` VARCHAR(67),
    `icd11Code` VARCHAR(28),
    `icd11Chapter` VARCHAR(122),
    `icd11Title` VARCHAR(403)
);

CREATE TABLE IF NOT EXISTS icd11_11To10MapToOneCategory (
    `Linearization_release_URI` VARCHAR(67),
    `icd11Code` VARCHAR(7),
    `icd11Chapter` VARCHAR(152),
    `icd11Title` VARCHAR(212),
    `icd10Code` VARCHAR(10),
    `icd10Chapter` VARCHAR(129),
    `icd10Title` VARCHAR(160)
);

CREATE TABLE IF NOT EXISTS icd11_foundation_10To11MapToOneCategory (
    `10ClassKind` VARCHAR(8),
    `10DepthInKind` VARCHAR(1),
    `icd10Code` VARCHAR(7),
    `icd10Chapter` VARCHAR(5),
    `icd10Title` VARCHAR(186),
    `ICD_11_FoundationURI` VARCHAR(39),
    `icd11Title` VARCHAR(299),
    `2024_Jan_21` VARCHAR(10),
    `Unknown` VARCHAR(2)
);

CREATE TABLE IF NOT EXISTS icd11_foundation_11To10MapToOneCategory (
    `Foundation_URI` VARCHAR(39),
    `icd11Code` VARCHAR(7),
    `icd11Chapter` VARCHAR(299),
    `icd11Title` VARCHAR(300),
    `icd10Code` VARCHAR(187),
    `icd10Title` VARCHAR(200)
);
SQL

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