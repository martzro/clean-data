#!/bin/bash

output="../../helper_files/filetracker.tsv"
mkdir -p temp_extracted

# Function to process extracted files
process_extracted_files() {
    local source="$1"
    for extracted_file in temp_extracted/*; do
        [ -e "$extracted_file" ] || continue  # Skip if no files
        base_name=$(basename "$extracted_file")

        if [ -e "$base_name" ]; then
            new_name="${base_name%.*}_2.${base_name##*.}"
            mv "$extracted_file" "$new_name"
            echo -e "$source\t$new_name" >> "$output"
        else
            mv "$extracted_file" .
            echo -e "$source\t$base_name" >> "$output"
        fi
    done
    rm -rf temp_extracted/*
}

# Process all zip files
for file in *.zip; do
    [ -e "$file" ] || continue
    echo "Processing ZIP: $file"
    unzip -o "$file" -d temp_extracted
    process_extracted_files "$file"
    rm "$file"
done

# Process all non-zipped folders
for dir in */; do
    dir_name="${dir%/}"
    [ -d "$dir_name" ] || continue
    [[ "$dir_name" == *.zip ]] && continue

    echo "Processing folder: $dir_name"
    cp -r "$dir_name"/* temp_extracted/ 2>/dev/null
    process_extracted_files "$dir_name"
    rm -rf "$dir_name"
done

# Cleanup
rmdir temp_extracted 2>/dev/null

# Recursively call if more .zip files or folders exist
shopt -s nullglob
zip_remaining=(*.zip)
folder_remaining=(*/*)

if (( ${#zip_remaining[@]} > 0 )) || (( ${#folder_remaining[@]} > 0 )); then
    echo "Recursing to handle remaining files..."
    exec "$0"
fi

