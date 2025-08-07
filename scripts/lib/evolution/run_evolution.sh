#!/bin/bash
# EVOSEAL Evolution Runner
# Unified interface for running evolution cycles

set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/../../.."

# Source logging functions
source "$ROOT_DIR/scripts/lib/utils/_logging.sh"

# Default values
ITERATIONS=10
TASK_FILE=""
CONFIG_FILE="$ROOT_DIR/config/evolution.yaml"
OUTPUT_DIR="$ROOT_DIR/output"
LOG_LEVEL="INFO"
DRY_RUN=0

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -i|--iterations)
            ITERATIONS="$2"
            shift 2
            ;;
        -t|--task-file)
            TASK_FILE="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -o|--output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -l|--log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            echo "EVOSEAL Evolution Runner"
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -i, --iterations NUM   Number of evolution iterations (default: 10)"
            echo "  -t, --task-file FILE   Path to task file (required)"
            echo "  -c, --config FILE      Path to config file (default: config/evolution.yaml)"
            echo "  -o, --output-dir DIR   Output directory (default: output)"
            echo "  -l, --log-level LEVEL  Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
            echo "  --dry-run              Show what would be done without making changes"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$TASK_FILE" ]; then
    print_error "Error: Task file is required. Use -t or --task-file to specify it."
    exit 1
fi

if [ ! -f "$TASK_FILE" ]; then
    print_error "Error: Task file not found: $TASK_FILE"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    print_warning "Config file not found: $CONFIG_FILE. Using defaults."
fi

# Set up environment
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"
export EVOSEAL_CONFIG="$CONFIG_FILE"
export LOG_LEVEL="$LOG_LEVEL"

# Create output directory
if [ $DRY_RUN -eq 0 ]; then
    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$OUTPUT_DIR/logs"
    mkdir -p "$OUTPUT_DIR/checkpoints"
fi

# Build command
EVOLVE_CMD=(
    "python" "-m" "evoseal.evolution.runner"
    "--iterations" "$ITERATIONS"
    "--task-file" "$TASK_FILE"
    "--output-dir" "$OUTPUT_DIR"
    "--log-level" "$LOG_LEVEL"
)

# Add dry-run flag if specified
if [ $DRY_RUN -eq 1 ]; then
    EVOLVE_CMD+=("--dry-run")
fi

# Log the command
print_status "Starting evolution with command:"
echo "  ${EVOLVE_CMD[*]}"

# Run the evolution
if [ $DRY_RUN -eq 0 ]; then
    # Redirect output to log file and console
    LOG_FILE="$OUTPUT_DIR/logs/evolution_$(date +%Y%m%d_%H%M%S).log"
    "${EVOLVE_CMD[@]}" 2>&1 | tee "$LOG_FILE"

    # Check exit status
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "Evolution completed successfully!"
        print_status "Log file: $LOG_FILE"
        print_status "Output directory: $OUTPUT_DIR"
    else
        print_error "Evolution failed. Check the log file for details: $LOG_FILE"
        exit 1
    fi
else
    print_status "Dry run complete. No changes were made."
fi

exit 0
