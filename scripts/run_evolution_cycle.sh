#!/bin/bash
# EVOSEAL Master Evolution Script
# Orchestrates the complete evolution cycle with proper error handling and logging

set -euo pipefail

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Import logging functions
source "$SCRIPT_DIR/_logging.sh"

# Configuration
LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
MAX_RETRIES=${MAX_RETRIES:-3}
RETRY_DELAY=${RETRY_DELAY:-60}
ITERATIONS=${ITERATIONS:-1}
TASK_FILE="${TASK_FILE:-$ROOT_DIR/tasks/default_task.json}"

# Ensure required directories exist
mkdir -p "$LOG_DIR"

# Set up logging
CURRENT_DATE=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/evolution_${CURRENT_DATE}.log"

exec > >(tee -a "$LOG_FILE") 2>&1

log_info "Starting EVOSEAL evolution cycle"
log_info "Logging to: $LOG_FILE"

# Function to run a phase with error handling
run_phase() {
    local phase_name="$1"
    local script_path="$2"
    shift 2
    
    log_info "Starting phase: $phase_name"
    
    if [ ! -f "$script_path" ]; then
        log_error "Script not found: $script_path"
        return 1
    fi
    
    if [ ! -x "$script_path" ]; then
        chmod +x "$script_path"
    fi
    
    if "$script_path" "$@"; then
        log_info "Phase completed: $phase_name"
        return 0
    else
        log_error "Phase failed: $phase_name"
        return 1
    fi
}

# Main execution
try {
    # 1. Environment setup
    run_phase "Environment Setup" "$SCRIPT_DIR/setup.sh"
    
    # 2. Update dependencies
    run_phase "Update Dependencies" "$SCRIPT_DIR/update_dependencies.sh"
    
    # 3. Sync learning datasets
    run_phase "Sync Learning Datasets" "$SCRIPT_DIR/sync_learning_datasets.sh"
    
    # 4. Run evolution cycles
    for ((i=1; i<=ITERATIONS; i++)); do
        log_info "Starting evolution cycle $i/$ITERATIONS"
        
        # 4.1 Run auto-evolution
        run_phase "Auto Evolution" "$SCRIPT_DIR/auto_evolve_and_push.sh" "$i" "$TASK_FILE"
        
        # 4.2 Run tests
        run_phase "Run Tests" "$SCRIPT_DIR/run_tests.sh"
        
        # 4.3 Generate documentation
        run_phase "Generate Documentation" "$SCRIPT_DIR/generate_release_files.sh"
        
        # 4.4 Clean up
        run_phase "Clean Up" "$SCRIPT_DIR/cleanup_metrics.py"
        
        log_info "Completed evolution cycle $i/$ITERATIONS"
    done
    
    # 5. Finalize release if needed
    if [ "${AUTO_RELEASE:-false}" = "true" ]; then
        run_phase "Prepare Release" "$SCRIPT_DIR/prepare_release.sh"
    fi
    
    log_info "EVOSEAL evolution cycle completed successfully"
    exit 0
    
} catch {
    log_error "EVOSEAL evolution cycle failed"
    exit 1
}
