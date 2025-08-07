#!/bin/bash
# EVOSEAL Unified Runner Script
# Consolidates multiple runner scripts into one flexible solution
# Supports service, continuous, and auto modes

set -euo pipefail

# Load configuration and logging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/evoseal-config.sh"
source "$SCRIPT_DIR/lib/utils/_logging.sh"

# Default configuration
DEFAULT_MODE="service"
DEFAULT_ITERATIONS=10
DEFAULT_TASK_FILE="tasks/default_task.json"
DEFAULT_WAIT_TIME=3600  # 1 hour between cycles
DEFAULT_UPDATE_INTERVAL=86400  # 24 hours between updates

# Parse command line arguments
MODE="$DEFAULT_MODE"
ITERATIONS="$DEFAULT_ITERATIONS"
TASK_FILE="$DEFAULT_TASK_FILE"
WAIT_TIME="$DEFAULT_WAIT_TIME"
UPDATE_INTERVAL="$DEFAULT_UPDATE_INTERVAL"

show_help() {
    cat << EOF
EVOSEAL Unified Runner - Consolidated service runner

Usage: $0 [options]

Options:
    --mode=service|continuous|auto    Runner mode (default: $DEFAULT_MODE)
    --iterations=N                    Number of iterations per cycle (default: $DEFAULT_ITERATIONS)
    --task-file=path                  Task file path (default: $DEFAULT_TASK_FILE)
    --wait-time=seconds               Wait time between cycles (default: $DEFAULT_WAIT_TIME)
    --update-interval=seconds         Update check interval (default: $DEFAULT_UPDATE_INTERVAL)
    --help                           Show this help message

Modes:
    service     - Run as systemd service with periodic updates and evolution cycles
    continuous  - Run continuous evolution cycles without auto-updates
    auto        - Full automation with updates, evolution, and version management

Examples:
    $0 --mode=service
    $0 --mode=continuous --iterations=5 --wait-time=1800
    $0 --mode=auto --update-interval=43200

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode=*)
            MODE="${1#*=}"
            shift
            ;;
        --iterations=*)
            ITERATIONS="${1#*=}"
            shift
            ;;
        --task-file=*)
            TASK_FILE="${1#*=}"
            shift
            ;;
        --wait-time=*)
            WAIT_TIME="${1#*=}"
            shift
            ;;
        --update-interval=*)
            UPDATE_INTERVAL="${1#*=}"
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate mode
case "$MODE" in
    service|continuous|auto)
        ;;
    *)
        log_error "Invalid mode: $MODE. Must be service, continuous, or auto"
        exit 1
        ;;
esac

# Set up logging for this run
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$EVOSEAL_LOGS/unified_runner_${MODE}_${TIMESTAMP}.log"

# Create a named pipe for logging
exec > >(tee -a "$LOG_FILE")
exec 2>&1

log_info "Logging to: $LOG_FILE"
log_info "Initializing EVOSEAL unified runner..."
log_info "Mode: $MODE"
log_info "Iterations per cycle: $ITERATIONS"
log_info "Wait time between cycles: $WAIT_TIME seconds"
log_info "Update check interval: $UPDATE_INTERVAL seconds"

# Ensure required directories exist
mkdir -p "$EVOSEAL_LOGS"
mkdir -p "$(dirname "$EVOSEAL_ROOT/$TASK_FILE")"

# Global variables for tracking
LAST_UPDATE_CHECK=0
CYCLE_COUNT=0

# Function to check if an update is needed
should_check_for_updates() {
    local current_time=$(date +%s)
    local time_since_last_update=$((current_time - LAST_UPDATE_CHECK))

    if [ $time_since_last_update -ge $UPDATE_INTERVAL ]; then
        return 0  # Yes, should update
    else
        return 1  # No, too soon
    fi
}

# Function to perform update check
perform_update_check() {
    log_info "Performing daily update check..."
    LAST_UPDATE_CHECK=$(date +%s)

    if execute_with_retry "$EVOSEAL_ROOT/scripts/update_evoseal.sh" 3 60; then
        log_info "Update check completed successfully"
        return 0
    else
        log_warn "Update check failed after retries"
        return 1
    fi
}

# Function to run evolution cycle
run_evolution_cycle() {
    local cycle_num=$1
    log_info "Starting evolution cycle #$cycle_num"

    if [ -f "$EVOSEAL_ROOT/scripts/run_evolution_cycle.sh" ]; then
        if execute_with_retry "$EVOSEAL_ROOT/scripts/run_evolution_cycle.sh" 2 30; then
            log_info "Evolution cycle #$cycle_num completed successfully"
            return 0
        else
            log_warn "Evolution cycle #$cycle_num failed"
            return 1
        fi
    else
        log_warn "Evolution cycle script not found, skipping"
        return 1
    fi
}

# Function to handle graceful shutdown
cleanup() {
    log_info "Received shutdown signal, cleaning up..."
    log_info "Unified runner shutting down gracefully"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Main execution logic based on mode
case "$MODE" in
    service)
        log_info "Starting service mode operation"

        # Initial update check
        if should_check_for_updates; then
            perform_update_check
        fi

        # Main service loop
        while true; do
            CYCLE_COUNT=$((CYCLE_COUNT + 1))

            # Check for updates periodically
            if should_check_for_updates; then
                perform_update_check
            fi

            # Run evolution cycle
            run_evolution_cycle $CYCLE_COUNT

            # Wait before next cycle
            log_info "Waiting $WAIT_TIME seconds before next cycle..."
            sleep $WAIT_TIME
        done
        ;;

    continuous)
        log_info "Starting continuous mode operation"
        log_info "Running $ITERATIONS evolution cycles with $WAIT_TIME second intervals"

        for ((i=1; i<=ITERATIONS; i++)); do
            run_evolution_cycle $i

            if [ $i -lt $ITERATIONS ]; then
                log_info "Waiting $WAIT_TIME seconds before next cycle..."
                sleep $WAIT_TIME
            fi
        done

        log_info "Continuous mode completed $ITERATIONS cycles"
        ;;

    auto)
        log_info "Starting auto mode operation"
        log_info "Full automation with updates, evolution, and version management"

        # Initial update
        perform_update_check

        # Main auto loop
        while true; do
            CYCLE_COUNT=$((CYCLE_COUNT + 1))

            # Periodic update checks
            if should_check_for_updates; then
                perform_update_check
            fi

            # Run evolution cycle
            run_evolution_cycle $CYCLE_COUNT

            # Additional auto-mode specific tasks could go here
            # (version management, release preparation, etc.)

            log_info "Waiting $WAIT_TIME seconds before next cycle..."
            sleep $WAIT_TIME
        done
        ;;
esac

log_info "EVOSEAL unified runner completed"
