#!/bin/bash
# EVOSEAL Service Installation Script
# Installs and configures the EVOSEAL systemd service

set -euo pipefail

# Import logging functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_logging.sh"

# Configuration
SERVICE_NAME="evoseal"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_USER=$(whoami)
EVOSEAL_DIR="$(dirname "$SCRIPT_DIR")"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "This script must be run as root"
    exit 1
fi

# Function to install required packages
install_dependencies() {
    log_info "Installing required packages..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv git jq
    
    # Install Python dependencies
    pip3 install -r "$EVOSEAL_DIR/requirements.txt"
}

# Function to set up the service
setup_service() {
    log_info "Setting up EVOSEAL service..."
    
    # Create a dedicated user for the service
    if ! id -u evoseal >/dev/null 2>&1; then
        log_info "Creating 'evoseal' user..."
        useradd -r -s /usr/sbin/nologin evoseal
    fi
    
    # Set ownership of EVOSEAL directory
    chown -R evoseal:evoseal "$EVOSEAL_DIR"
    
    # Make scripts executable
    chmod +x "$EVOSEAL_DIR/scripts/"*.sh
    
    # Install the service file
    log_info "Installing service file to $SERVICE_FILE..."
    cp "$EVOSEAL_DIR/scripts/evoseal.service" "$SERVICE_FILE"
    
    # Update paths in the service file
    sed -i "s|/home/kade/EVOSEAL|$EVOSEAL_DIR|g" "$SERVICE_FILE"
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable and start the service
    systemctl enable "$SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"
    
    log_info "EVOSEAL service installed and started successfully"
    log_info "To view logs: journalctl -u $SERVICE_NAME -f"
}

# Main execution
log_info "Starting EVOSEAL service installation..."

install_dependencies
setup_service

log_success "EVOSEAL installation completed successfully"
log_info "Service status: systemctl status $SERVICE_NAME"
