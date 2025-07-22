#!/bin/bash

# EVOSEAL Project Evolution Script
# This script applies EVOSEAL to evolve an external project
# Usage: ./evolve_project.sh [config_file] [iterations]

set -e

CONFIG_FILE=${1:-"project_config.json"}
ITERATIONS=${2:-10}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="logs/projects"
RESULTS_DIR="results/projects"

mkdir -p "$LOG_DIR"
mkdir -p "$RESULTS_DIR"

LOG_FILE="$LOG_DIR/evolution_${TIMESTAMP}.log"
RESULT_FILE="$RESULTS_DIR/result_${TIMESTAMP}.json"

echo "Starting project evolution with EVOSEAL" | tee -a "$LOG_FILE"
echo "Configuration: $CONFIG_FILE" | tee -a "$LOG_FILE"
echo "Iterations: $ITERATIONS" | tee -a "$LOG_FILE"
echo "Timestamp: $TIMESTAMP" | tee -a "$LOG_FILE"

# Check if config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Error: Configuration file '$CONFIG_FILE' not found." | tee -a "$LOG_FILE"
  echo "Creating a template configuration file at 'project_config.json'..."
  cp templates/project_evolution.json project_config.json
  echo "Please edit project_config.json with your project details and run this script again."
  exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
  echo "Error: jq is required but not installed. Please install it first." | tee -a "$LOG_FILE"
  exit 1
fi

# Extract project details from config
PROJECT_NAME=$(jq -r '.name' "$CONFIG_FILE")
REPO_URL=$(jq -r '.project.repository' "$CONFIG_FILE")
LOCAL_PATH=$(jq -r '.project.local_path' "$CONFIG_FILE")
BRANCH=$(jq -r '.project.branch' "$CONFIG_FILE")
BASE_BRANCH=$(jq -r '.project.base_branch' "$CONFIG_FILE")

echo "Project: $PROJECT_NAME" | tee -a "$LOG_FILE"
echo "Repository: $REPO_URL" | tee -a "$LOG_FILE"
echo "Local path: $LOCAL_PATH" | tee -a "$LOG_FILE"

# Get current EVOSEAL version
function get_current_version() {
  grep -oP 'version = "\K[^"]+' pyproject.toml | head -n 1
}
CURRENT_VERSION=$(get_current_version)
echo "EVOSEAL version: $CURRENT_VERSION" | tee -a "$LOG_FILE"

# Setup EVOSEAL
source .venv/bin/activate || { echo "Error: Virtual environment activation failed"; exit 1; }

# Refresh EVOSEAL version in case virtual environment changes it
CURRENT_VERSION=$(get_current_version)

# Function to prepare the project repository
function prepare_project() {
  echo "Preparing project repository..." | tee -a "$LOG_FILE"
  
  # If local path doesn't exist, clone the repository
  if [[ ! -d "$LOCAL_PATH" ]]; then
    echo "Cloning repository to $LOCAL_PATH..." | tee -a "$LOG_FILE"
    mkdir -p "$(dirname "$LOCAL_PATH")"
    git clone "$REPO_URL" "$LOCAL_PATH"
    cd "$LOCAL_PATH"
  else
    echo "Using existing repository at $LOCAL_PATH..." | tee -a "$LOG_FILE"
    cd "$LOCAL_PATH"
    
    # Check if repo is clean
    if [[ -n $(git status --porcelain) ]]; then
      echo "Warning: Repository has uncommitted changes." | tee -a "$LOG_FILE"
      read -p "Do you want to continue anyway? (y/n): " -r
      if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborting evolution process." | tee -a "$LOG_FILE"
        exit 1
      fi
    fi
    
    # Update repository
    echo "Updating repository..." | tee -a "$LOG_FILE"
    git fetch origin
  fi
  
  # Check if evolution branch exists
  if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    echo "Evolution branch $BRANCH exists, checking it out..." | tee -a "$LOG_FILE"
    git checkout "$BRANCH"
    git pull origin "$BASE_BRANCH"
  else
    echo "Creating evolution branch $BRANCH from $BASE_BRANCH..." | tee -a "$LOG_FILE"
    git checkout "$BASE_BRANCH"
    git pull origin "$BASE_BRANCH"
    git checkout -b "$BRANCH"
  fi
  
  cd - > /dev/null
  echo "Repository prepared successfully." | tee -a "$LOG_FILE"
}

# Function to run the initial evaluation
function evaluate_project() {
  echo "Running project evaluation..." | tee -a "$LOG_FILE"
  
  local metrics_file="$RESULTS_DIR/metrics_${TIMESTAMP}.json"
  echo "{\"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\", \"metrics\": {}}" > "$metrics_file"
  
  # Extract and run each metric command
  jq -c '.evaluation.metrics[]' "$CONFIG_FILE" | while read -r metric; do
    local name=$(echo "$metric" | jq -r '.name')
    local tool=$(echo "$metric" | jq -r '.tool')
    local cmd=$(echo "$metric" | jq -r '.command' | sed "s|{target_dir}|$LOCAL_PATH|g" | sed "s|{project_path}|$LOCAL_PATH|g")
    local threshold=$(echo "$metric" | jq -r '.threshold')
    
    echo "Running metric: $name using $tool..." | tee -a "$LOG_FILE"
    echo "Command: $cmd" | tee -a "$LOG_FILE"
    
    # Run the command and capture output
    local result_output
    if result_output=$(eval "$cmd" 2>&1); then
      echo "Metric $name executed successfully." | tee -a "$LOG_FILE"
      
      # Process result based on tool type
      local metric_value
      case "$tool" in
        "pylint")
          # Extract average score from pylint JSON output
          metric_value=$(echo "$result_output" | jq -r '.summary.score')
          ;;
        "pytest")
          # Extract coverage percentage
          metric_value=$(echo "$result_output" | jq -r '.totals.percent_covered')
          ;;
        "custom")
          # Read from specified result file
          local result_file=$(echo "$metric" | jq -r '.result_file' | sed "s|{project_path}|$LOCAL_PATH|g")
          if [[ -f "$result_file" ]]; then
            metric_value=$(jq -r '.score' "$result_file")
          else
            echo "Error: Custom result file $result_file not found." | tee -a "$LOG_FILE"
            metric_value="N/A"
          fi
          ;;
        *)
          # Default: try to extract a number from the output
          metric_value=$(echo "$result_output" | grep -oP '\d+(\.\d+)?')
          ;;
      esac
      
      echo "Metric value: $metric_value (threshold: $threshold)" | tee -a "$LOG_FILE"
      
      # Add to metrics file
      local tmp_file=$(mktemp)
      jq --arg name "$name" --arg value "$metric_value" --arg threshold "$threshold" \
        '.metrics[$name] = {"value": $value, "threshold": $threshold}' "$metrics_file" > "$tmp_file"
      mv "$tmp_file" "$metrics_file"
      
    else
      echo "Error running metric $name:" | tee -a "$LOG_FILE"
      echo "$result_output" | tee -a "$LOG_FILE"
    fi
  done
  
  echo "Evaluation complete. Results saved to $metrics_file" | tee -a "$LOG_FILE"
  cp "$metrics_file" "$RESULTS_DIR/latest_metrics.json"
}

# Function to run EVOSEAL evolution on the project
function evolve_project() {
  echo "Starting EVOSEAL evolution process..." | tee -a "$LOG_FILE"
  
  # Create task file for the external project
  local task_file="$RESULTS_DIR/task_${TIMESTAMP}.json"
  
  # Extract focus areas and target files
  local focus_areas=$(jq -r '.evolution.focus_areas | join(",")' "$CONFIG_FILE")
  local target_files=$(jq -r '.evolution.target_files | join(" ")' "$CONFIG_FILE")
  
  # Create temporary task file
  cat > "$task_file" << EOF
{
  "name": "${PROJECT_NAME} Evolution",
  "description": "Evolve ${PROJECT_NAME} codebase to improve ${focus_areas}",
  "type": "external_project_evolution",
  "project_path": "${LOCAL_PATH}",
  "parameters": {
    "max_iterations": ${ITERATIONS},
    "evaluation_metrics": $(jq '.evaluation.metrics | map(.name)' "$CONFIG_FILE"),
    "focus_areas": $(jq '.evolution.focus_areas' "$CONFIG_FILE"),
    "target_files": $(jq '.evolution.target_files' "$CONFIG_FILE")
  },
  "constraints": {
    "safety_boundaries": true,
    "rollback_enabled": true,
    "max_changes_per_iteration": $(jq '.safety.max_file_changes_per_iteration' "$CONFIG_FILE"),
    "max_line_changes_per_file": $(jq '.safety.max_line_changes_per_file' "$CONFIG_FILE"),
    "restricted_files": $(jq '.safety.restricted_files' "$CONFIG_FILE")
  }
}
EOF
  
  echo "Task file created at $task_file" | tee -a "$LOG_FILE"
  
  # Run EVOSEAL with the external project task
  echo "Running EVOSEAL pipeline with project task..." | tee -a "$LOG_FILE"
  evoseal "$CURRENT_VERSION" pipeline init "$LOCAL_PATH" --force | tee -a "$LOG_FILE"
  evoseal "$CURRENT_VERSION" pipeline config --task-file "$task_file" | tee -a "$LOG_FILE"
  evoseal "$CURRENT_VERSION" pipeline config --set iterations="$ITERATIONS" | tee -a "$LOG_FILE"
  evoseal "$CURRENT_VERSION" pipeline config --set external.project=true | tee -a "$LOG_FILE"
  evoseal "$CURRENT_VERSION" pipeline config --set external.path="$LOCAL_PATH" | tee -a "$LOG_FILE"
  
  # Start the evolution process
  echo "Starting evolution with $ITERATIONS iterations..." | tee -a "$LOG_FILE"
  evoseal "$CURRENT_VERSION" pipeline start | tee -a "$LOG_FILE"
  
  # Export results
  echo "Exporting results..." | tee -a "$LOG_FILE"
  evoseal "$CURRENT_VERSION" export --output="$RESULT_FILE" | tee -a "$LOG_FILE"
  cp "$RESULT_FILE" "$RESULTS_DIR/latest_results.json"
}

# Function to process the evolution results
function process_results() {
  echo "Processing evolution results..." | tee -a "$LOG_FILE"
  
  # Check if we should commit changes
  local auto_commit=$(jq -r '.version_control.auto_commit' "$CONFIG_FILE")
  
  if [[ "$auto_commit" == "true" ]]; then
    echo "Auto-commit enabled. Committing changes to the repository..." | tee -a "$LOG_FILE"
    
    # Get commit message template
    local commit_template=$(jq -r '.version_control.commit_message_template' "$CONFIG_FILE")
    
    # Generate commit message from results
    local improvement_type=$(jq -r '.primary_improvement' "$RESULT_FILE")
    local component=$(jq -r '.components[0]' "$RESULT_FILE")
    local detailed_changes=$(jq -r '.changes_summary' "$RESULT_FILE")
    
    # Replace placeholders
    local commit_message="${commit_template/\{improvement_type\}/$improvement_type}"
    commit_message="${commit_message/\{component\}/$component}"
    commit_message="${commit_message/\{detailed_changes\}/$detailed_changes}"
    
    # Commit changes
    cd "$LOCAL_PATH"
    git add .
    git commit -m "$commit_message"
    
    # Check if we should create a pull request
    local auto_pr=$(jq -r '.version_control.pull_request.auto_create' "$CONFIG_FILE")
    if [[ "$auto_pr" == "true" ]]; then
      echo "Auto-PR enabled. However, PR creation requires GitHub CLI or similar tool."
      echo "Please implement the PR creation step manually or extend this script."
    fi
    
    cd - > /dev/null
  else
    echo "Auto-commit disabled. Changes remain uncommitted in the working directory." | tee -a "$LOG_FILE"
  fi
  
  # Run re-evaluation to compare before and after
  echo "Re-evaluating project after evolution..." | tee -a "$LOG_FILE"
  evaluate_project
  
  echo "Evolution process complete!" | tee -a "$LOG_FILE"
  echo "Results saved to $RESULT_FILE" | tee -a "$LOG_FILE"
}

# Main execution flow
prepare_project
evaluate_project
evolve_project
process_results

echo "Project evolution completed successfully." | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE"
