#!/bin/bash
# EVOSEAL Utilities - Common tasks

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/../../.."
source "$ROOT_DIR/scripts/lib/utils/_logging.sh"

# Main commands
clean() {
    print_status "Cleaning build artifacts..."
    rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist" "$ROOT_DIR/*.egg-info"
    find "$ROOT_DIR" -type d -name "__pycache__" -exec rm -r {} +
    find "$ROOT_DIR" -type d -name ".pytest_cache" -exec rm -r {} +
    print_success "Clean complete!"
}

lint() {
    print_status "Running linters..."
    command -v flake8 && flake8 "$ROOT_DIR/evoseal"
    command -v mypy && mypy "$ROOT_DIR/evoseal"
    print_success "Linting complete!"
}

format() {
    print_status "Formatting code..."
    command -v black && black "$ROOT_DIR/evoseal"
    command -v isort && isort "$ROOT_DIR/evoseal"
    print_success "Formatting complete!"
}

# Show help
show_help() {
    echo "EVOSEAL Utilities"
    echo "Usage: $0 <command>"
    echo "  clean    - Remove build artifacts"
    echo "  lint     - Run code linters"
    echo "  format   - Format code"
    echo "  help     - Show this help"
}

# Main
case "${1:-help}" in
    clean) clean ;;
    lint) lint ;;
    format) format ;;
    *) show_help ;;
esac

exit 0
