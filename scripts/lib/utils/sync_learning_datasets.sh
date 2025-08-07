#!/bin/bash

# Script to synchronize learning datasets for EVOSEAL
# Usage: ./sync_learning_datasets.sh [config_file]

set -e

CONFIG_FILE=${1:-"config/learning_datasets.json"}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/dataset_sync_$TIMESTAMP.log"

mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date)] Starting dataset synchronization" | tee -a "$LOG_FILE"

# Check if jq is installed
if ! command -v jq &> /dev/null; then
  echo "Error: jq is required but not installed. Please install it first." | tee -a "$LOG_FILE"
  exit 1
fi

# Function to sync a Git repository
sync_git_repo() {
  local name=$1
  local url=$2
  local path=$3
  local patterns=$4
  local excludes=$5

  echo "Syncing dataset: $name from $url" | tee -a "$LOG_FILE"

  mkdir -p "$path"
  local tmp_dir="/tmp/evoseal_dataset_$name"

  # Clone or update repository
  if [ -d "$tmp_dir" ]; then
    echo "Updating existing repository for $name..." | tee -a "$LOG_FILE"
    git -C "$tmp_dir" fetch --quiet
    git -C "$tmp_dir" reset --hard origin/main --quiet
  else
    echo "Cloning repository for $name..." | tee -a "$LOG_FILE"
    git clone --depth=1 "$url" "$tmp_dir" --quiet
  fi

  # Create patterns file for rsync
  local patterns_file="/tmp/evoseal_patterns_$name"
  echo "$patterns" | jq -r '.[]' > "$patterns_file"

  # Create exclude file for rsync
  local exclude_file="/tmp/evoseal_excludes_$name"
  echo "$excludes" | jq -r '.[]' > "$exclude_file"

  # Sync files to the target path
  echo "Copying files to $path..." | tee -a "$LOG_FILE"
  rsync -av --include-from="$patterns_file" --exclude-from="$exclude_file" \
    --prune-empty-dirs "$tmp_dir/" "$path/" --quiet

  # Create metadata file
  echo "Creating metadata for $name..." | tee -a "$LOG_FILE"
  {
    echo "# $name Dataset"
    echo "Source: $url"
    echo "Last synchronized: $(date)"
    echo "Description: $(jq -r --arg name "$name" '.datasets[] | select(.name==$name) | .description' "$CONFIG_FILE")"
  } > "$path/README.md"

  echo "Dataset $name synchronized successfully" | tee -a "$LOG_FILE"
}

# Process each dataset from the configuration file
echo "Reading configuration from $CONFIG_FILE" | tee -a "$LOG_FILE"

# Process git repositories
jq -c '.datasets[]' "$CONFIG_FILE" | while read -r dataset; do
  name=$(echo "$dataset" | jq -r '.name')
  path=$(echo "$dataset" | jq -r '.path')
  url=$(echo "$dataset" | jq -r '.url')
  patterns=$(echo "$dataset" | jq -r '.extraction.patterns')
  excludes=$(echo "$dataset" | jq -r '.extraction.exclude')

  sync_git_repo "$name" "$url" "$path" "$patterns" "$excludes"
done

# Create directories for custom data sources
jq -c '.custom_directories[]' "$CONFIG_FILE" | while read -r dir; do
  name=$(echo "$dir" | jq -r '.name')
  path=$(echo "$dir" | jq -r '.path')
  description=$(echo "$dir" | jq -r '.description')

  echo "Setting up custom directory: $name at $path" | tee -a "$LOG_FILE"
  mkdir -p "$path"

  # Create metadata file
  {
    echo "# $name Custom Dataset"
    echo "Last updated: $(date)"
    echo "Description: $description"
    echo ""
    echo "## Usage Instructions"
    echo "Place relevant code examples, documentation, and training data in this directory."
    echo "The directory structure should follow these conventions:"
    echo ""
    echo "- `examples/`: Working code examples"
    echo "- `docs/`: Documentation and explanations"
    echo "- `data/`: Sample data (small files only)"
  } > "$path/README.md"

  echo "Custom directory $name prepared" | tee -a "$LOG_FILE"
done

# Update EVOSEAL config to include these paths
CONFIG_YAML=".evoseal/config.yaml"
if [[ -f "$CONFIG_YAML" ]]; then
  echo "Updating EVOSEAL configuration..." | tee -a "$LOG_FILE"

  # Get all dataset paths
  dataset_paths=$(jq -r '.datasets[].path' "$CONFIG_FILE")
  custom_paths=$(jq -r '.custom_directories[].path' "$CONFIG_FILE")

  # Create a temporary file for the new configuration
  tmp_config=$(mktemp)

  # Read each line of the config file
  found_knowledge_paths=false
  while IFS= read -r line; do
    echo "$line" >> "$tmp_config"

    # If this is the knowledge_paths section, add our paths
    if [[ "$line" == "knowledge_paths:" ]]; then
      found_knowledge_paths=true

      # Add dataset paths
      for path in $dataset_paths; do
        if ! grep -q "$path" "$CONFIG_YAML"; then
          echo "    - $path" >> "$tmp_config"
        fi
      done

      # Add custom paths
      for path in $custom_paths; do
        if ! grep -q "$path" "$CONFIG_YAML"; then
          echo "    - $path" >> "$tmp_config"
        fi
      done
    fi
  done < "$CONFIG_YAML"

  # If knowledge_paths section wasn't found, add it at the end
  if [ "$found_knowledge_paths" = false ]; then
    echo "" >> "$tmp_config"
    echo "knowledge_paths:" >> "$tmp_config"

    # Add dataset paths
    for path in $dataset_paths; do
      echo "  - $path" >> "$tmp_config"
    done

    # Add custom paths
    for path in $custom_paths; do
      echo "  - $path" >> "$tmp_config"
    done
  fi

  # Replace the original config file
  mv "$tmp_config" "$CONFIG_YAML"
fi

echo "Dataset synchronization completed at $(date)" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE"
