#!/bin/bash

# Check if a directory was passed as an argument
if [ -z "$1" ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

BASE_DIR="$1"

# Check if the directory exists
if [ ! -d "$BASE_DIR" ]; then
    echo "Directory not found: $BASE_DIR"
    exit 1
fi

find "$BASE_DIR" -type f -name "*.yaml" | sort | while read -r yaml_file; do
    echo "Running: $yaml_file"
    
    python3 src/run.py --config "$yaml_file"
    wait $!

    # Check for failure
    if [ $? -ne 0 ]; then
        echo "Failed on: $yaml_file"
        exit 1 
    fi
done