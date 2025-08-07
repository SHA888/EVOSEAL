#!/bin/bash
# Update _logging.sh paths in all scripts

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find all shell scripts and update _logging.sh paths
find "$SCRIPT_DIR" -type f -name "*.sh" -o -name "evoseal" | while read -r file; do
    # Skip files in .git directories
    if [[ "$file" == *".git"* ]]; then
        continue
    fi

    # Check if the file contains a reference to _logging.sh
    if grep -q "_logging\.sh" "$file"; then
        echo "Updating _logging.sh path in $file"

        # Update relative paths to use the new location
        sed -i 's|"\([^"]*\)\.\./\.\./scripts/_logging\.sh"|"\1lib/utils/lib/utils/_logging.sh"|g' "$file"
        sed -i 's|"\([^"]*\)_logging\.sh"|"\1lib/utils/lib/utils/_logging.sh"|g' "$file"

        # Update direct references in the same directory
        sed -i 's|"\([^"]*\)\.\./_logging\.sh"|"\1../lib/utils/lib/utils/_logging.sh"|g' "$file"
        sed -i 's|"\([^"]*\)\./_logging\.sh"|"\1../lib/utils/lib/utils/_logging.sh"|g' "$file"
    fi
done

echo "Finished updating _logging.sh paths"
