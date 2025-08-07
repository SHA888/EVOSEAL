#!/bin/bash
# EVOSEAL Deployment Script
# Unified deployment interface for EVOSEAL

set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/../../.."

# Source logging functions
source "$ROOT_DIR/scripts/lib/utils/_logging.sh"

# Default values
ENVIRONMENT="development"
SERVICE_TYPE="all"
CONFIG_FILE="$ROOT_DIR/config/deployment/$ENVIRONMENT.yaml"
DRY_RUN=0
FORCE=0

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--environment)
            ENVIRONMENT="$2"
            CONFIG_FILE="$ROOT_DIR/config/deployment/$ENVIRONMENT.yaml"
            shift 2
            ;;
        -t|--type)
            SERVICE_TYPE="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -f|--force)
            FORCE=1
            shift
            ;;
        -h|--help)
            echo "EVOSEAL Deployment Script"
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV  Deployment environment (default: development)"
            echo "  -t, --type TYPE        Service type (api, worker, all) (default: all)"
            echo "  -c, --config FILE      Path to config file"
            echo "  --dry-run              Show what would be done without making changes"
            echo "  -f, --force            Force deployment even if there are uncommitted changes"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate environment
if [ ! -f "$CONFIG_FILE" ]; then
    print_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

# Check for uncommitted changes
if [ $FORCE -eq 0 ] && [ -n "$(git status --porcelain)" ]; then
    print_error "Error: You have uncommitted changes. Use --force to deploy anyway."
    exit 1
fi

# Load configuration
print_status "Loading configuration from $CONFIG_FILE"
# shellcheck source=/dev/null
source "$CONFIG_FILE"

# Set up environment
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"
DEPLOY_LOG="$ROOT_DIR/logs/deploy_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$DEPLOY_LOG")"

# Deployment functions
deploy_api() {
    print_status "Deploying API service..."

    if [ $DRY_RUN -eq 1 ]; then
        print_status "[DRY RUN] Would deploy API service"
        return 0
    fi

    # Stop existing service if running
    if systemctl --user is-active --quiet evoseal-api.service; then
        print_status "Stopping existing API service..."
        systemctl --user stop evoseal-api.service
    fi

    # Install dependencies
    print_status "Installing dependencies..."
    pip install -r "$ROOT_DIR/requirements.txt"

    # Run database migrations if needed
    if [ -f "$ROOT_DIR/manage.py" ]; then
        print_status "Running database migrations..."
        python "$ROOT_DIR/manage.py" migrate
    fi

    # Start the service
    print_status "Starting API service..."
    systemctl --user start evoseal-api.service

    print_success "API service deployed successfully!"
}

deploy_worker() {
    print_status "Deploying worker service..."

    if [ $DRY_RUN -eq 1 ]; then
        print_status "[DRY RUN] Would deploy worker service"
        return 0
    fi

    # Stop existing worker if running
    if systemctl --user is-active --quiet evoseal-worker.service; then
        print_status "Stopping existing worker service..."
        systemctl --user stop evoseal-worker.service
    fi

    # Start the worker
    print_status "Starting worker service..."
    systemctl --user start evoseal-worker.service

    print_success "Worker service deployed successfully!"
}

# Main deployment logic
main() {
    print_status "Starting deployment to $ENVIRONMENT environment..."

    case "$SERVICE_TYPE" in
        api)
            deploy_api
            ;;
        worker)
            deploy_worker
            ;;
        all)
            deploy_api
            deploy_worker
            ;;
        *)
            print_error "Invalid service type: $SERVICE_TYPE"
            exit 1
            ;;
    esac

    print_success "Deployment completed successfully!"
}

# Run the deployment
main 2>&1 | tee "$DEPLOY_LOG"

# Check exit status
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    print_success "Deployment log: $DEPLOY_LOG"
else
    print_error "Deployment failed. Check the log for details: $DEPLOY_LOG"
    exit 1
fi

exit 0
