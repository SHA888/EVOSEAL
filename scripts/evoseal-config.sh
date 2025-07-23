#!/bin/bash
# EVOSEAL Configuration
# This file contains default paths and settings that can be overridden by environment variables

# Base directory (one level up from scripts directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVOSEAL_DIR="$(dirname "$SCRIPT_DIR")"

# Default configuration
export EVOSEAL_HOME="${EVOSEAL_HOME:-$EVOSEAL_DIR}"
export EVOSEAL_VENV="${EVOSEAL_VENV:-$EVOSEAL_DIR/.venv}"
export EVOSEAL_LOGS="${EVOSEAL_LOGS:-$EVOSEAL_DIR/logs}"
export EVOSEAL_DATA="${EVOSEAL_DATA:-$EVOSEAL_DIR/data}"

# Service configuration
export EVOSEAL_SERVICE_NAME="${EVOSEAL_SERVICE_NAME:-evoseal.service}"

# Python configuration
export PYTHONPATH="${PYTHONPATH:-$EVOSEAL_DIR:$EVOSEAL_DIR/SEAL}"

# Ensure all directories exist
mkdir -p "$EVOSEAL_LOGS"
mkdir -p "$EVOSEAL_DATA"

# Export PATH to include virtual environment
export PATH="$EVOSEAL_VENV/bin:$PATH"

# Load environment-specific settings if available
if [ -f "$EVOSEAL_DIR/.evoseal.local" ]; then
    source "$EVOSEAL_DIR/.evoseal.local"
fi
