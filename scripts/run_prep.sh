#!/bin/bash

NEW_COLUMN_FILE="../helper_files/newcolumns.csv"
LOGS="../scripts/logs.csv"
output="../helper_files/filetracker.tsv"

: > "$output"

venv="venv"
if [[ ! -d "$venv" ]]; then
    echo "no virtual environment, making"
    python -m venv venv
    source "$venv/Scripts/activate"
    pip install -r requirements.txt
    exit
fi

source "$venv/Scripts/activate"

set -e  # Exit on any error

cd data || { echo "❌ Failed to change directory to ../data"; exit 1; }

echo -n "" > "$NEW_COLUMN_FILE"
echo -n "" > "$LOGS"
echo -n "" > "$output"

log_step() {
    echo -e "\n\033[1;34m▶ $1...\033[0m"
    START_TIME=$(date +%s)
}

log_done() {
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo -e "\033[1;32m✔ Done ($DURATION sec)\033[0m"
}

for dir in */; do
    log_step "Unzipping files"
    cd "$dir"
    ../../scripts/unzip.sh
    log_done

    log_step "Converting XLSX to CSV"
    ../../scripts/xlsx2csv.sh
    log_done

    log_step "Checking CSV columns"
    ../../scripts/checkColumns.sh
    log_done
    cd ../
done