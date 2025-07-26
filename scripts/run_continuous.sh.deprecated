#!/bin/bash
# run_continuous.sh - Script to run EVOSEAL continuously
# 
# Usage: ./run_continuous.sh [iterations] [task_file]
#
# This script runs EVOSEAL in a continuous loop, with automatic restart if it crashes
# 

# Load environment variables
source "$(dirname "$(dirname "$(readlink -f "$0")")")/.env"

# Initialize variables
ITERATIONS=${1:-10}
TASK_FILE=${2:-"./tasks/default_task.json"}
LOG_DIR="./logs"

# Get current version from pyproject.toml
function get_current_version() {
  grep -oP 'version = "\K[^"]+' pyproject.toml | head -n 1
}

# Get current EVOSEAL version to use in commands
CURRENT_VERSION=$(get_current_version)
echo "Using EVOSEAL version $CURRENT_VERSION"
LOG_FILE="$LOG_DIR/evoseal_$(date +%Y%m%d_%H%M%S).log"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

echo "Starting EVOSEAL continuous run..."
echo "Iterations: $ITERATIONS"
echo "Task file: $TASK_FILE"
echo "Logs: $LOG_FILE"

# Ensure we're in the correct directory
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"

# Activate virtual environment
source .venv/bin/activate

# Initial configuration
echo "Setting up initial configuration..."
evoseal $CURRENT_VERSION config set seal.model gpt-4
evoseal $CURRENT_VERSION config set evolve.population_size 50

# Function to handle unexpected exits
cleanup() {
  echo "Caught signal, shutting down EVOSEAL gracefully..."
  evoseal $CURRENT_VERSION stop all
  exit 0
}

# Register signal handlers
trap cleanup SIGINT SIGTERM

# Main loop to keep EVOSEAL running continuously
while true; do
  echo "$(date) - Starting EVOSEAL run" | tee -a "$LOG_FILE"
  
  # Run pipeline
  evoseal $CURRENT_VERSION pipeline init "." --force | tee -a "$LOG_FILE"
  evoseal $CURRENT_VERSION pipeline config --set "iterations=$ITERATIONS" | tee -a "$LOG_FILE"
  evoseal $CURRENT_VERSION pipeline start | tee -a "$LOG_FILE"
  
  # Monitor until completion or failure
  while true; do
    STATUS=$(evoseal $CURRENT_VERSION pipeline status | grep "Status:" | awk '{print $2}')
    if [[ "$STATUS" == "COMPLETED" ]]; then
      echo "$(date) - Pipeline completed successfully" | tee -a "$LOG_FILE"
      break
    elif [[ "$STATUS" == "FAILED" ]]; then
      echo "$(date) - Pipeline failed, restarting..." | tee -a "$LOG_FILE"
      evoseal $CURRENT_VERSION pipeline stop | tee -a "$LOG_FILE"
      break
    fi
    sleep 30  # Check status every 30 seconds
  done
  
  # Export results
  RESULT_FILE="./results/evoseal_$(date +%Y%m%d_%H%M%S).json"
  mkdir -p ./results
  echo "Exporting results to $RESULT_FILE" | tee -a "$LOG_FILE"
  evoseal $CURRENT_VERSION export results "$RESULT_FILE" | tee -a "$LOG_FILE"
  
  echo "Waiting 60 seconds before starting next run..." | tee -a "$LOG_FILE"
  sleep 60
done
