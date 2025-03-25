#!/bin/bash
for file in *.zip; do
    echo "Processing: $file"
    
    # Unzip the file into the current directory
    unzip -o "$file" -d temp_extracted
    
    # Handle duplicates
    for extracted_file in temp_extracted/*; do
        base_name=$(basename "$extracted_file")
        
        # Check if the file already exists in the target directory
        if [ -e "$base_name" ]; then
            mv "$extracted_file" "${base_name%.*}_2.${base_name##*.}"
        else
            mv "$extracted_file" .
        fi
    done
    rm "$file"
done

# Cleanup temporary directory
rmdir temp_extracted

