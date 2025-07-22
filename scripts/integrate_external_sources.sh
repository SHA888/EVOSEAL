#!/bin/bash

# Script to integrate external sources for EVOSEAL learning
# Usage: ./integrate_external_sources.sh [target_directory]

set -e

# Default target directory
TARGET_DIR=${1:-"data/external_sources"}
REPOS_FILE="config/external_repositories.txt"
CACHE_DIR="data/cache"

# Create directories if they don't exist
mkdir -p "$TARGET_DIR"
mkdir -p "$CACHE_DIR"
mkdir -p "$(dirname "$REPOS_FILE")"

# Initialize repositories file if it doesn't exist
if [[ ! -f "$REPOS_FILE" ]]; then
  echo "# External repositories for EVOSEAL learning" > "$REPOS_FILE"
  echo "# Format: repository_url,branch,subdirectory,description" >> "$REPOS_FILE"
  echo "# Example: https://github.com/example/repo.git,main,src,Example machine learning framework" >> "$REPOS_FILE"
  echo "https://github.com/huggingface/transformers.git,main,src/transformers,Huggingface Transformers library" >> "$REPOS_FILE"
  echo "https://github.com/pytorch/pytorch.git,main,torch,PyTorch core library" >> "$REPOS_FILE"
fi

# Function to process a repository
function process_repository() {
  local repo_url=$1
  local branch=$2
  local subdir=$3
  local description=$4
  
  # Extract repo name from URL
  local repo_name=$(basename "$repo_url" .git)
  local repo_dir="$CACHE_DIR/$repo_name"
  local target_subdir="$TARGET_DIR/$repo_name"
  
  echo "Processing repository: $description ($repo_url)"
  
  # Clone or update repository
  if [[ -d "$repo_dir" ]]; then
    echo "Updating existing repository..."
    git -C "$repo_dir" fetch --depth=1
    git -C "$repo_dir" reset --hard "origin/$branch"
  else
    echo "Cloning new repository..."
    git clone --depth=1 --branch "$branch" "$repo_url" "$repo_dir"
  fi
  
  # Create target directory for this repo
  mkdir -p "$target_subdir"
  
  # Copy relevant files (exclude git, large binaries, etc.)
  echo "Extracting relevant knowledge from $subdir..."
  rsync -av --exclude=".git" --exclude="*.bin" --exclude="*.pt" \
    --exclude="*.pth" --exclude="*.onnx" --exclude="*.h5" \
    "$repo_dir/$subdir/" "$target_subdir/"
  
  # Generate a summary file
  echo "# $repo_name - $description" > "$target_subdir/SOURCE_INFO.md"
  echo "Source: $repo_url" >> "$target_subdir/SOURCE_INFO.md"
  echo "Branch: $branch" >> "$target_subdir/SOURCE_INFO.md"
  echo "Last updated: $(date)" >> "$target_subdir/SOURCE_INFO.md"
  echo "" >> "$target_subdir/SOURCE_INFO.md"
  echo "## Directory Structure" >> "$target_subdir/SOURCE_INFO.md"
  find "$target_subdir" -type f -name "*.py" | sort | sed 's|'"$target_subdir"'|.|g' >> "$target_subdir/SOURCE_INFO.md"
  
  echo "Finished processing $repo_name"
}

# Process each repository in the configuration file
echo "Starting external source integration..."

while IFS=',' read -r repo branch subdir description || [[ -n "$repo" ]]; do
  # Skip comments and empty lines
  if [[ -z "$repo" || "$repo" =~ ^# ]]; then
    continue
  fi
  
  # Process this repository
  process_repository "$repo" "$branch" "$subdir" "$description"
done < "$REPOS_FILE"

echo "Integration complete. External sources available in $TARGET_DIR"

# Update the EVOSEAL configuration to include these sources
CONFIG_FILE=".evoseal/config.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
  # Check if external_sources is already in the knowledge_paths
  if ! grep -q "external_sources" "$CONFIG_FILE"; then
    echo "Updating EVOSEAL configuration to include external sources..."
    sed -i '/knowledge_paths:/a \    - data/external_sources' "$CONFIG_FILE"
  fi
fi

echo "Done!"
