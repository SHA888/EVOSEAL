#!/bin/bash

# Load logging functions
source "$(dirname "$0")/_logging.sh"

# Set default values
LOG_LEVEL=${LOG_LEVEL:-INFO}
MAX_RETRIES=${MAX_RETRIES:-3}
RETRY_DELAY=${RETRY_DELAY:-60}
ITERATIONS=${ITERATIONS:-1}

# Set up logging
timestamp=$(date +"%Y%m%d_%H%M%S")
log_file="${LOG_FILE:-logs/evolution_${timestamp}.log}"
mkdir -p "$(dirname "$log_file")"

exec > >(tee -a "$log_file") 2>&1

log_info "Starting EVOSEAL evolution cycle"
log_info "Logging to: $log_file"

# Function to handle errors
error_handler() {
    local line_number=$1
    local error_code=$2
    log_error "Error in ${BASH_SOURCE[1]} at line $line_number with exit code $error_code"
    log_error "EVOSEAL evolution cycle failed"
    exit $error_code
}

# Set up error handling
trap 'error_handler ${LINENO} $?' ERR

# Function to run a phase
run_phase() {
    local phase_name="$1"
    local script_path="scripts/${phase_name}.sh"

    log_info "Starting phase: $phase_name"

    if [ -f "$script_path" ]; then
        if bash "$script_path"; then
            log_info "Phase completed: $phase_name"
            return 0
        else
            log_error "Phase failed: $phase_name"
            return 1
        fi
    else
        log_warn "Script not found: $script_path"
        return 0
    fi
}

# Main execution
log_info "Starting main execution"

# Run each phase
for phase in "setup" "update_dependencies" "sync_learning_datasets" "evolve" "test" "document" "release" "cleanup"; do
    if ! run_phase "$phase"; then
        log_error "Stopping execution due to failure in phase: $phase"
        exit 1
    fi
done

log_info "EVOSEAL evolution cycle completed successfully"
exit 0
