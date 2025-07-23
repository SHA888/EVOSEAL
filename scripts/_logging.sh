#!/bin/bash
# Logging utilities for EVOSEAL scripts

# Log levels
LOG_LEVEL_DEBUG=0
LOG_LEVEL_INFO=1
LOG_LEVEL_WARN=2
LOG_LEVEL_ERROR=3

# Default log level (can be overridden)
LOG_LEVEL=${LOG_LEVEL:-$LOG_LEVEL_INFO}

# ANSI color codes
NC='\033[0m' # No Color
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'

# Log functions
log_debug() {
    if [ "$LOG_LEVEL" -le $LOG_LEVEL_DEBUG ]; then
        echo -e "${BLUE}[DEBUG]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
    fi
}

log_info() {
    if [ "$LOG_LEVEL" -le $LOG_LEVEL_INFO ]; then
        echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
    fi
}

log_warn() {
    if [ "$LOG_LEVEL" -le $LOG_LEVEL_WARN ]; then
        echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
    fi
}

log_error() {
    if [ "$LOG_LEVEL" -le $LOG_LEVEL_ERROR ]; then
        echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
    fi
}

# Function to execute a command with logging and error handling
# Usage: run_command "command" ["error_message"]
run_command() {
    local cmd="$1"
    local error_msg="${2:-Command failed: $1}"
    
    log_debug "Executing: $cmd"
    if eval "$cmd"; then
        log_debug "Command succeeded: $cmd"
        return 0
    else
        log_error "$error_msg"
        return 1
    fi
}

# Function to retry a command
# Usage: retry_command max_attempts delay "command" ["error_message"]
retry_command() {
    local max_attempts=$1
    local delay=$2
    local cmd=$3
    local error_msg="${4:-Command failed after $max_attempts attempts: $cmd}"
    
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if run_command "$cmd" "Attempt $attempt/$max_attempts failed"; then
            return 0
        fi
        
        attempt=$((attempt + 1))
        if [ $attempt -le $max_attempts ]; then
            log_info "Retrying in ${delay} seconds..."
            sleep $delay
        fi
    done
    
    log_error "$error_msg"
    return 1
}
