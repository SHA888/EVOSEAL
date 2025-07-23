#!/bin/bash

# Update script for EVOSEAL
set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/evoseal-config.sh"

# Set up logging
LOG_FILE="$EVOSEAL_LOGS/update_$(date +%Y%m%d_%H%M%S).log"

# Log file will be created by the configuration script

echo "[$(date)] Starting EVOSEAL update" | tee -a "$LOG_FILE"

# Function to log messages
log() {
    echo "[$(date)] $1" | tee -a "$LOG_FILE"
}

# Check if service is running
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "Stopping $SERVICE_NAME..."
    sudo systemctl stop "$SERVICE_NAME" || {
        log "Failed to stop $SERVICE_NAME"
        exit 1
    }
fi

# Change to repository directory
cd "$EVOSEAL_HOME" || {
    log "Failed to change to repository directory: $EVOSEAL_HOME"
    exit 1
}

# Stash any local changes that would prevent pulling
git stash push --include-untracked --message "Auto-stash before update $(date +%Y%m%d_%H%M%S)" &>> "$LOG_FILE"

# Pull latest changes
log "Pulling latest changes from repository..."
git pull origin main &>> "$LOG_FILE" || {
    log "Failed to pull latest changes"
    exit 1
}

# Update submodules
log "Updating submodules..."
git submodule update --init --recursive &>> "$LOG_FILE" || {
    log "Failed to update submodules"
    exit 1
}

# Activate virtual environment
log "Activating virtual environment at $EVOSEAL_VENV..."
if [ -f "$EVOSEAL_VENV/bin/activate" ]; then
    source "$EVOSEAL_VENV/bin/activate" || {
        log "Failed to activate virtual environment at $EVOSEAL_VENV"
        exit 1
    }
else
    log "Virtual environment not found at $EVOSEAL_VENV, trying to create one..."
    python3 -m venv "$EVOSEAL_VENV" || {
        log "Failed to create virtual environment at $EVOSEAL_VENV"
        exit 1
    }
    source "$EVOSEAL_VENV/bin/activate"
fi

# Install/update dependencies
log "Installing/updating Python dependencies..."
log "Using Python: $(which python3)"
log "Python version: $(python3 --version)"

# Ensure pip is up to date
python3 -m pip install --upgrade pip &>> "$LOG_FILE" || {
    log "Warning: Failed to update pip"
}

# Install the package in development mode
python3 -m pip install -e . &>> "$LOG_FILE" || {
    log "Failed to install/update Python dependencies"
    exit 1
}

# Install any new system dependencies if needed
if [ -f "$REPO_DIR/requirements-system.txt" ]; then
    log "Installing system dependencies..."
    sudo apt-get update &>> "$LOG_FILE"
    xargs -a "$REPO_DIR/requirements-system.txt" sudo apt-get install -y &>> "$LOG_FILE"
fi

# Restart the service if it exists
if systemctl list-units --full -all | grep -Fq "$EVOSEAL_SERVICE_NAME"; then
    log "Restarting $EVOSEAL_SERVICE_NAME..."
    sudo systemctl daemon-reload
    sudo systemctl restart "$EVOSEAL_SERVICE_NAME" || {
        log "Warning: Failed to restart $EVOSEAL_SERVICE_NAME"
        # Continue even if service restart fails
    }
else
    log "Service $EVOSEAL_SERVICE_NAME not found, skipping service restart"
fi

log "Update completed successfully!"
exit 0
