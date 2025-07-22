#!/bin/bash
#
# EVOSEAL Auto-Evolution and Push
# This script runs EVOSEAL, exports results, and auto-commits/pushes improvements
#

set -e

# Activate virtual environment immediately
source "$(dirname "$(readlink -f "$0")")/../.venv/bin/activate"

# Load environment variables
source "$(dirname "$(readlink -f "$0")")/../.env"

# Default settings
ITERATIONS=${1:-10}
TASK_FILE=${2:-"./tasks/default_task.json"}
LOG_DIR="./logs"
RESULTS_DIR="./results"
WAIT_TIME=60  # seconds between cycles
IMPROVEMENT_THRESHOLD=0.15  # minimum improvement required to trigger a version bump

# Ensure directories exist
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
  
  git add pyproject.toml results/ .evoseal/
  git commit -m "Auto-update to v$new_version - Evolution cycle completed at $timestamp"
  git tag -a "v$new_version" -m "EVOSEAL v$new_version - Auto-generated after successful evolution"
  git push origin main
  git push origin "v$new_version"
  
  echo "✅ Successfully pushed version $new_version to GitHub"
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

# Initialize EVOSEAL
function setup_evoseal() {
  # Activate virtual environment if not already activated
  if [[ -z "${VIRTUAL_ENV}" ]]; then
    source .venv/bin/activate
  fi
  
  # Re-get the version after activation to ensure correct version
  CURRENT_VERSION=$(get_current_version)
  echo "Current EVOSEAL version: $CURRENT_VERSION"
  
  # Set up configurations
  echo "Setting up initial configuration..."
  evoseal $CURRENT_VERSION config set seal.model gpt-4 | grep "✅" || true
  evoseal $CURRENT_VERSION config set evolve.population_size 50 | grep "✅" || true
}

# Main loop
echo "Starting EVOSEAL auto-evolution and push cycle..."
echo "Iterations per cycle: $ITERATIONS"
echo "Task file: $TASK_FILE"
echo "Log directory: $LOG_DIR"
echo "Results directory: $RESULTS_DIR"

# Initial setup
setup_evoseal
current_version=$(get_current_version)
echo "Starting with version: $current_version"

# Continuous operation loop
while true; do
  # Get timestamp for this run
  timestamp=$(date +"%Y%m%d_%H%M%S")
  log_file="$LOG_DIR/evoseal_$timestamp.log"
  result_file="$RESULTS_DIR/result_$timestamp.json"
  
  echo "$(date) - Starting EVOSEAL run" | tee -a "$log_file"
  
  # Run pipeline
  evoseal $CURRENT_VERSION pipeline init "." --force | tee -a "$log_file"
  evoseal $CURRENT_VERSION pipeline config --set "iterations=$ITERATIONS" | tee -a "$log_file"
  evoseal $CURRENT_VERSION pipeline start | tee -a "$log_file"
  
  # Export results
  echo "$(date) - Exporting results" | tee -a "$log_file"
  evoseal $CURRENT_VERSION export --output="$result_file" | tee -a "$log_file"
  
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
    commit_and_push $new_version
    
    echo "$(date) - Cycle complete. Version updated to $new_version." | tee -a "$log_file"
  else
    echo "$(date) - No significant improvement detected. Continuing with current version." | tee -a "$log_file"
  fi
  
  # Wait before next cycle
  echo "$(date) - Waiting for $WAIT_TIME seconds before next cycle..." | tee -a "$log_file"
  sleep $WAIT_TIME
done
