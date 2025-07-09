#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

LOGS="logs.log"
DB_FILE="db.db"
outname="cleaned_data"
outrows=500000

# Parse named arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --outname)
            outname="$2"
            shift 2
            ;;
        --rowcount)
            outrows="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--outname NAME] [--rowcount COUNT]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage."
            exit 1
            ;;
    esac
done

# Clear logs
: > "$LOGS"

venv="venv"
if [[ ! -d "$venv" ]]; then
    echo "no virtual environment, making"
    python -m venv venv
    source "$venv/Scripts/activate"
    pip install -r requirements.txt
    exit
fi

# Drop tables if DB exists
if [[ -f "$DB_FILE" ]]; then
    echo "Cleaning up existing database: $DB_FILE"
    python - <<EOF
import sqlite3

con = sqlite3.connect("$DB_FILE")
cur = con.cursor()
for table in ("staging", "final", "aggregated"):
    cur.execute(f"DROP TABLE IF EXISTS {table}")
cur.execute("VACUUM")
con.close()
EOF
fi

# Logging helpers
log_step() {
    echo -e "\n\033[1;34m▶ $1...\033[0m"
    STEP_START=$(date +%s)
}

log_done() {
    local STEP_END=$(date +%s)
    local DURATION=$((STEP_END - STEP_START))
    echo -e "\033[1;32m✔ Done ($DURATION sec)\033[0m"
}

# Run main script
log_step "Running Python script"
source "$venv/Scripts/activate"
python -m main "$outname" "$outrows"
log_done