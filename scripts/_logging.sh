#!/bin/bash

# Logging utility for EVOSEAL
# Combines features from both versions with enhanced functionality

# Define colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log levels (numeric)
LOG_LEVEL_DEBUG=0
LOG_LEVEL_INFO=1
LOG_LEVEL_WARN=2
LOG_LEVEL_ERROR=3
LOG_LEVEL_FATAL=4

# Default log level
LOG_LEVEL=${LOG_LEVEL:-INFO}

# Set default log level
LOG_LEVEL_NUM=$LOG_LEVEL_INFO

# Convert log level string to number
get_log_level_num() {
    case "${1^^}" in
        "DEBUG") echo $LOG_LEVEL_DEBUG ;;
        "INFO") echo $LOG_LEVEL_INFO ;;
        "WARN") echo $LOG_LEVEL_WARN ;;
        "ERROR") echo $LOG_LEVEL_ERROR ;;
        "FATAL") echo $LOG_LEVEL_FATAL ;;
        *) echo $LOG_LEVEL_INFO ;;
    esac
}

# Set log level
set_log_level() {
    LOG_LEVEL_NUM=$(get_log_level_num "$1")
}

# Get current timestamp
get_timestamp() {
    date +"%Y-%m-%d %T"
}

# Log a message with level and color
log() {
    local level=$1
    local color=$2
    local message=$3
    local timestamp=$(get_timestamp)

    local level_num=$(get_log_level_num "$level")
    if [ $level_num -ge $LOG_LEVEL_NUM ]; then
        echo -e "${color}[${level}] ${timestamp} - ${message}${NC}"
    fi
}

# Log levels
log_debug() {
    log "DEBUG" "$BLUE" "$@"
}

log_info() {
    log "INFO" "$GREEN" "$@"
}

log_warn() {
    log "WARN" "$YELLOW" "$@"
}

log_error() {
    log "ERROR" "$RED" "$@"
}

log_fatal() {
    log "FATAL" "$RED" "$@"
    exit 1
}

# Function to execute a command with retries
# Usage: execute_with_retry "command" [max_retries] [retry_delay]
execute_with_retry() {
    local cmd="$1"
    local max_retries=${2:-3}
    local retry_delay=${3:-5}
    local attempt=1
    local exit_code=0

    while [ $attempt -le $max_retries ]; do
        log_info "Attempt $attempt of $max_retries: $cmd"

        # Execute the command and capture the exit code
        if output=$($cmd 2>&1); then
            log_info "Command succeeded on attempt $attempt"
            echo "$output"
            return 0
        else
            exit_code=$?
            log_warn "Command failed with exit code $exit_code on attempt $attempt"
            log_warn "Command output: $output"
        fi

        # Increment attempt counter
        attempt=$((attempt + 1))

        # If we have retries left, wait before retrying
        if [ $attempt -le $max_retries ]; then
            log_info "Retrying in $retry_delay seconds..."
            sleep $retry_delay
        fi
    done

    # If we get here, all retries failed
    log_error "Command failed after $max_retries attempts"
    return $exit_code
}

# Function to execute a command with logging and error handling
# Usage: run_command "command" ["error_message"]
run_command() {
    local cmd="$1"
    local error_msg="${2:-Command failed: $cmd}"

    log_info "Executing: $cmd"

    # Execute the command and capture output
    if output=$($cmd 2>&1); then
        log_info "Command succeeded"
        echo "$output"
        return 0
    else
        log_error "$error_msg"
        log_error "Command output: $output"
        return 1
    fi
}

# Function to retry a command
# Alias to execute_with_retry for backward compatibility
# Usage: retry_command max_attempts delay "command" ["error_message"]
retry_command() {
    local max_attempts=$1
    local delay=$2
    local cmd="$3"
    local error_msg="${4:-Command failed after $max_attempts attempts}"

    if execute_with_retry "$cmd" "$max_attempts" "$delay"; then
        return 0
    else
        log_error "$error_msg"
        return 1
    fi
}

# Set default log level from environment variable if set
if [ -n "$LOG_LEVEL" ]; then
    set_log_level "$LOG_LEVEL"
fi

# Log script start
log_info "Script started: $(basename "$0")"
