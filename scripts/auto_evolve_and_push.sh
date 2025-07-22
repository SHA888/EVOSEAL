#!/bin/bash
#
# EVOSEAL Auto-Evolution and Push
# This script handles the complete automation of EVOSEAL including:
# 1. Code updates and dependency management
# 2. Running evolution cycles
# 3. Version management and releases
# 4. GitHub integration and pushing changes
#
# Usage: ./auto_evolve_and_push.sh [iterations] [task_file]
#

set -e

# Activate virtual environment immediately
source "$(dirname "$(readlink -f "$0")")/../.venv/bin/activate"

# Configuration with environment variable fallbacks
ITERATIONS=${1:-${EVOSEAL_ITERATIONS:-10}}  # Default to 10 iterations if not specified
TASK_FILE=${2:-${EVOSEAL_TASK_FILE:-"./tasks/default_task.json"}}  # Default task file
LOG_DIR="${EVOSEAL_LOGS_DIR:-./logs}"
RESULTS_DIR="${EVOSEAL_RESULTS_DIR:-./results}"
RELEASES_DIR="${EVOSEAL_RELEASES_DIR:-./releases}"
WAIT_TIME=300  # seconds between cycles (5 minutes)
IMPROVEMENT_THRESHOLD=0.15  # minimum improvement required to trigger a version bump
MAX_RETRIES=3  # maximum number of retries for failed operations
RETRY_DELAY=60  # seconds to wait before retrying failed operations

# Get project root directory
PROJECT_ROOT="$(dirname "$(readlink -f "$0")")/.."
cd "$PROJECT_ROOT" || { echo "Failed to change to project root directory"; exit 1; }
mkdir -p "$LOG_DIR"
mkdir -p "$RESULTS_DIR"

# Trap for graceful shutdown
trap cleanup SIGINT SIGTERM
function cleanup() {
  echo "Caught signal, shutting down EVOSEAL gracefully..."
  echo "Stopping all EVOSEAL processes..."
  evoseal $CURRENT_VERSION process stop-all || echo "Stop all is not yet implemented."
  exit 0
}

# Get current version from pyproject.toml
function get_current_version() {
  grep -oP 'version = "\K[^"]+' pyproject.toml | head -n 1
}

# Get current EVOSEAL version to use in commands
CURRENT_VERSION=$(get_current_version)

# Increment patch version (x.y.z -> x.y.z+1)
function increment_version() {
  local version=$1
  local major=$(echo $version | cut -d. -f1)
  local minor=$(echo $version | cut -d. -f2)
  local patch=$(echo $version | cut -d. -f3)
  patch=$((patch + 1))
  echo "$major.$minor.$patch"
}

# Update version in pyproject.toml
function update_version() {
  local new_version=$1
  sed -i "s/version = \"[0-9.]*\"/version = \"$new_version\"/" pyproject.toml
}

# Commit and push changes with new version
function commit_and_push() {
  local new_version=$1
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  local retry_count=0
  
  # Create releases directory if it doesn't exist
  mkdir -p "$RELEASES_DIR"
  
  # Generate release notes
  local release_notes="$RELEASES_DIR/release_notes_${new_version}.md"
  echo "# EVOSEAL v$new_version" > "$release_notes"
  echo "Released on $timestamp" >> "$release_notes"
  echo "" >> "$release_notes"
  echo "## Changes" >> "$release_notes"
  git log --pretty=format:"- %s" "v${CURRENT_VERSION}..HEAD" >> "$release_notes" 2>/dev/null || echo "- Initial release" >> "$release_notes"
  
  # Stage all changes
  git add .
  
  # Create a new commit
  while [ $retry_count -lt $MAX_RETRIES ]; do
    if git commit -m "Auto-update to v$new_version - Evolution cycle completed at $timestamp"; then
      break
    else
      echo "Commit failed, retrying..."
      sleep $RETRY_DELAY
      ((retry_count++))
    fi
  done
  
  if [ $retry_count -eq $MAX_RETRIES ]; then
    echo "Failed to create commit after $MAX_RETRIES attempts"
    return 1
  fi
  
  # Create an annotated tag
  git tag -a "v$new_version" -m "EVOSEAL v$new_version - Auto-generated after successful evolution"
  
  # Push changes with retry logic
  retry_count=0
  while [ $retry_count -lt $MAX_RETRIES ]; do
    if git push origin main && git push origin "v$new_version"; then
      echo "✅ Successfully pushed version $new_version to GitHub"
      return 0
    else
      echo "Push failed, retrying..."
      sleep $RETRY_DELAY
      ((retry_count++))
    fi
  done
  
  echo "Failed to push changes after $MAX_RETRIES attempts"
  return 1
}

# Check if significant improvement was made
function check_improvement() {
  local latest_result="$RESULTS_DIR/latest_metrics.json"
  local previous_result="$RESULTS_DIR/previous_metrics.json"
  
  # If no previous metrics, consider as improvement
  if [ ! -f "$previous_result" ]; then
    cp "$latest_result" "$previous_result"
    return 0
  fi
  
  # Compare metrics - simple version just looks for overall_score
  # This could be enhanced with a more sophisticated comparison
  local new_score=$(grep -oP '"overall_score":\s*\K[0-9.]+' "$latest_result" || echo "0")
  local old_score=$(grep -oP '"overall_score":\s*\K[0-9.]+' "$previous_result" || echo "0")
  
  # Calculate improvement percentage
  local improvement=$(echo "$new_score - $old_score" | bc)
  
  echo "Previous score: $old_score, New score: $new_score, Improvement: $improvement"
  
  # If improvement exceeds threshold, consider significant
  if (( $(echo "$improvement > $IMPROVEMENT_THRESHOLD" | bc -l) )); then
    cp "$latest_result" "$previous_result"
    return 0
  else
    return 1
  fi
}

# Initialize EVOSEAL with retry logic
function setup_evoseal() {
  local retry_count=0
  
  while [ $retry_count -lt $MAX_RETRIES ]; do
    # Activate virtual environment if not already activated
    if [[ -z "${VIRTUAL_ENV}" ]]; then
      source .venv/bin/activate || {
        echo "Failed to activate virtual environment, retrying..."
        sleep $RETRY_DELAY
        ((retry_count++))
        continue
      }
    fi
    
    # Re-get the version after activation to ensure correct version
    CURRENT_VERSION=$(get_current_version)
    echo "Current EVOSEAL version: $CURRENT_VERSION"
    
    # Set up configurations
    echo "Setting up initial configuration..."
    evoseal $CURRENT_VERSION config set seal.model gpt-4 | grep "✅" || true
    evoseal $CURRENT_VERSION config set evolve.population_size 50 | grep "✅" || true
    
    # Verify setup was successful
    if [ $? -eq 0 ]; then
      return 0
    else
      echo "Setup failed, retrying..."
      sleep $RETRY_DELAY
      ((retry_count++))
    fi
  done
  
  echo "Failed to set up EVOSEAL after $MAX_RETRIES attempts"
  return 1
}

# Main execution function
function main() {
  echo "Starting EVOSEAL auto-evolution and push cycle..."
  echo "Iterations: $ITERATIONS"
  echo "Task file: $TASK_FILE"
  echo "Log directory: $LOG_DIR"
  echo "Results directory: $RESULTS_DIR"
  echo "Releases directory: $RELEASES_DIR"

  # Initial setup
  setup_evoseal || { echo "Failed to set up EVOSEAL"; exit 1; }
  current_version=$(get_current_version)
  echo "Starting with version: $current_version"

  # Create necessary directories
  mkdir -p "$LOG_DIR" "$RESULTS_DIR" "$RELEASES_DIR"

  # Continuous operation loop
  while true; do
    # Get timestamp for this run
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local log_file="$LOG_DIR/evoseal_$timestamp.log"
    local result_file="$RESULTS_DIR/result_$timestamp.json"
    
    echo "$(date) - Starting EVOSEAL run" | tee -a "$log_file"
    
    # Run pipeline with retry logic
    local pipeline_success=false
    for ((i=1; i<=$MAX_RETRIES; i++)); do
      echo "$(date) - Running EVOSEAL pipeline (Attempt $i/$MAX_RETRIES)" | tee -a "$log_file"
      
      # Initialize pipeline
      if evoseal $CURRENT_VERSION pipeline init "." --force | tee -a "$log_file" && \
         evoseal $CURRENT_VERSION pipeline config --set "iterations=$ITERATIONS" | tee -a "$log_file" && \
         evoseal $CURRENT_VERSION pipeline start | tee -a "$log_file"; then
        pipeline_success=true
        break
      else
        echo "$(date) - Pipeline failed, retrying in $RETRY_DELAY seconds..." | tee -a "$log_file"
        sleep $RETRY_DELAY
      fi
    done
    
    if [ "$pipeline_success" = false ]; then
      echo "$(date) - Failed to run pipeline after $MAX_RETRIES attempts" | tee -a "$log_file"
      sleep $WAIT_TIME
      continue
    fi
    
    # Export results
    echo "$(date) - Exporting results" | tee -a "$log_file"
    if ! evoseal $CURRENT_VERSION export --output="$result_file" | tee -a "$log_file"; then
      echo "$(date) - Failed to export results" | tee -a "$log_file"
      sleep $WAIT_TIME
      continue
    fi
    
    # Copy to latest for comparison
    cp "$result_file" "$RESULTS_DIR/latest_metrics.json"
    
    # Check if significant improvement was made
    if check_improvement; then
      echo "$(date) - Significant improvement detected" | tee -a "$log_file"
      
      # Increment version
      current_version=$(get_current_version)
      new_version=$(increment_version $current_version)
      update_version $new_version
      
      echo "$(date) - Updated version from $current_version to $new_version" | tee -a "$log_file"
      
      # Commit and push
      if commit_and_push $new_version; then
        # After successful push, update the service if needed
        update_service_config $new_version
      fi
      
      echo "$(date) - Cycle complete. Version updated to $new_version." | tee -a "$log_file"
    else
      echo "$(date) - No significant improvement detected. Continuing with current version." | tee -a "$log_file"
    fi
    
    # Wait before next cycle
    echo "$(date) - Waiting for $WAIT_TIME seconds before next cycle..." | tee -a "$log_file"
    sleep $WAIT_TIME
  done
}

# Function to update service configuration if needed
function update_service_config() {
  local version=$1
  local service_file="/etc/systemd/system/evoseal.service"
  local script_path="$(pwd)/scripts/auto_evolve_and_push.sh"
  local task_file="$(pwd)/tasks/default_task.json"
  
  # Only update if the service file exists and we have write permissions
  if [ -f "$service_file" ] && [ -w "$service_file" ]; then
    echo "Updating service configuration to use version $version..."
    
    # Create a backup of the current service file
    sudo cp "$service_file" "${service_file}.bak"
    
    # Update the ExecStart line with the current paths
    sudo sed -i "s|ExecStart=.*auto_evolve_and_push.sh .*|ExecStart=$script_path $ITERATIONS $task_file|g" "$service_file"
    
    # Ensure proper permissions
    sudo chown root:root "$service_file"
    sudo chmod 644 "$service_file"
    
    # Reload systemd to apply changes
    sudo systemctl daemon-reload
    sudo systemctl restart evoseal
    
    echo "Service configuration updated to use version $version"
  else
    echo "Warning: Could not update service configuration. Make sure you have the necessary permissions."
    echo "You may need to manually update $service_file with the following ExecStart line:"
    echo "ExecStart=$script_path $ITERATIONS $task_file"
  fi
}

# Start the main function
main "$@"
