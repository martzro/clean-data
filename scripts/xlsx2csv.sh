#!/bin/bash

# activate virtual env
source ../clean-data/Scripts/activate
# Path to the Python script
PYTHON_SCRIPT="../scripts/xlsx2csv.py"

# Check if the Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Python script '$PYTHON_SCRIPT' not found."
    deactivate
    exit 1
fi

# Iterate over all .xlsx files in the current directory
for excel_file in *.xls*; do
    # Check if there are any .xlsx files
    if [ ! -e "$excel_file" ]; then
        echo "No Excel files found in the current directory."
        exit 1
    fi

    echo "Processing file: $excel_file"
    
    # Call the Python script with the file name
    python "$PYTHON_SCRIPT" "$excel_file"

    # Check if the Python script ran successfully
    if [ $? -eq 0 ]; then
        # Remove the Excel file after successful processing
        echo "Removing file: $excel_file"
        rm "$excel_file"
    else
        echo "Error processing file: $excel_file. Skipping removal."
    fi
done

deactivate
echo "All files have been processed!"

