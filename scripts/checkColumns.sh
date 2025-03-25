#!/bin/bash


REFERENCE_CSV="../../helper_files/column_names.csv"
NEW_COLUMN_FILE="../../helper_files/newcolumns.csv"
LOGS="../../scripts/logs.csv"

# Check if the reference CSV exists
if [ ! -f "$REFERENCE_CSV" ]; then
    echo "Error: Reference file '$REFERENCE_CSV' not found."
    exit 1
fi

# Read the reference column names into an array (convert to uppercase for case-insensitive checks)
reference_columns=()
while IFS=, read -r column; do
    reference_columns+=("$(echo "$column")")
done < <(cut -d, -f1 "$REFERENCE_CSV") # Read the first column

# Initialize an empty file to store new columns
#echo -n "" > "$NEW_COLUMN_FILE"
#echo -n "" > "$LOGS"


# Iterate over all CSV files in the current directory
for file in *.csv; do
    # Skip newcolumn.csv
    if [[ "$file" == "$NEW_COLUMN_FILE" ]]; then
        continue
    fi

    echo "Processing file: $file"

    # Check if the file is empty
    if [ ! -s "$file" ]; then
        echo "File '$file' is empty. Deleting it."
        rm "$file"
        continue
    fi

    # Read the header (first row) of the CSV
    header=$(head -n 1 "$file")
    if [ -z "$header" ]; then
        echo "File '$file' has no header. Deleting it."
        rm "$file"
        continue
    fi

    # Loop through headers and check if they exist in the reference
    IFS=, read -ra file_columns <<< "$header" # Split headers into an array
    for column in "${file_columns[@]}"; do
        # Convert the column to uppercase for case-insensitive comparison
        trimmed_column=$(echo "$column" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | tr '[:lower:]' '[:upper:]')
        match_found=false
        for ref_column in "${reference_columns[@]}"; do
            if [[ "$trimmed_column" == "$ref_column" ]]; then
                match_found=true
                break
            fi
        done

        # If the column is not in the reference, add it to NEW_COLUMN_FILE
        if [ "$match_found" = false ]; then
            # Check case-insensitively if the column is already in NEW_COLUMN_FILE
            if ! grep -q -i "$trimmed_column" "$NEW_COLUMN_FILE"; then
                echo "$trimmed_column" >> "$NEW_COLUMN_FILE"
                echo "$trimmed_column,$file" >> "$LOGS"
            fi
        fi
    done
done

echo "Processing complete. Missing columns are listed in :$NEW_COLUMN_FILE."