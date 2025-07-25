#!/bin/bash
# Wrapper script to run semgrep from its dedicated virtual environment

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate the semgrep virtual environment
source "$SCRIPT_DIR/../.semgrep-venv/bin/activate"

# Run semgrep with all arguments passed to this script
semgrep "$@"

# Deactivate the virtual environment
deactivate
