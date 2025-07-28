#!/bin/bash
# EVOSEAL Service Installation Script
# Installs and configures the EVOSEAL systemd service (user or system mode)

set -euo pipefail

# Import logging functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_logging.sh"
source "$SCRIPT_DIR/evoseal-config.sh"

# Configuration
SERVICE_NAME="evoseal"
SCRIPT_USER=$(whoami)
EVOSEAL_DIR="$(dirname "$SCRIPT_DIR")"

# Determine installation mode
INSTALL_MODE="${1:-user}"  # Default to user mode

if [ "$INSTALL_MODE" != "user" ] && [ "$INSTALL_MODE" != "system" ]; then
    log_error "Invalid installation mode: $INSTALL_MODE. Use 'user' or 'system'"
    echo "Usage: $0 [user|system]"
    echo "  user   - Install as user service (recommended, no root required)"
    echo "  system - Install as system service (requires root)"
    exit 1
fi

# Check permissions based on mode
if [ "$INSTALL_MODE" = "system" ] && [ "$EUID" -ne 0 ]; then
    log_error "System installation requires root privileges"
    log_info "Run with sudo or use 'user' mode instead"
    exit 1
fi

if [ "$INSTALL_MODE" = "user" ] && [ "$EUID" -eq 0 ]; then
    log_warn "Running user installation as root is not recommended"
    log_info "Consider running as regular user instead"
fi

# Function to install required packages
install_dependencies() {
    log_info "Installing required packages..."

    if [ "$INSTALL_MODE" = "system" ]; then
        # System-wide installation
        apt-get update
        apt-get install -y python3 python3-pip python3-venv git jq
    else
        # User installation - check if packages are available
        log_info "Checking for required packages (user mode)..."
        for pkg in python3 python3-pip python3-venv git jq; do
            if ! command -v "$pkg" >/dev/null 2>&1; then
                log_warn "Package $pkg not found. You may need to install it manually."
            else
                log_info "✅ $pkg is available"
            fi
        done
    fi

    # Set up virtual environment and install Python dependencies
    log_info "Setting up Python virtual environment..."
    cd "$EVOSEAL_DIR"

    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        log_info "Created virtual environment"
    fi

    source .venv/bin/activate

    # Install dependencies
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        log_info "Installed Python dependencies"
    elif [ -f "requirements/pinned_requirements.txt" ]; then
        pip install -r requirements/pinned_requirements.txt
        log_info "Installed pinned Python dependencies"
    else
        pip install -e .
        log_info "Installed package in development mode"
    fi
}

# Function to set up the service
setup_service() {
    log_info "Setting up EVOSEAL service in $INSTALL_MODE mode..."

    # Make scripts executable
    chmod +x "$EVOSEAL_DIR/scripts/"*.sh

    if [ "$INSTALL_MODE" = "system" ]; then
        setup_system_service
    else
        setup_user_service
    fi
}

# Function to set up system service
setup_system_service() {
    local SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

    # Create a dedicated user for the service
    if ! id -u evoseal >/dev/null 2>&1; then
        log_info "Creating 'evoseal' user..."
        useradd -r -s /usr/sbin/nologin evoseal
    fi

    # Set ownership of EVOSEAL directory
    chown -R evoseal:evoseal "$EVOSEAL_DIR"

    # Install the service file
    log_info "Installing system service file to $SERVICE_FILE..."
    cp "$EVOSEAL_DIR/scripts/evoseal.service" "$SERVICE_FILE"

    # Update placeholders in the service file
    sed -i "s|__EVOSEAL_ROOT__|$EVOSEAL_DIR|g" "$SERVICE_FILE"
    sed -i "s|__EVOSEAL_USER__|evoseal|g" "$SERVICE_FILE"

    # Reload systemd
    systemctl daemon-reload

    # Enable and start the service
    systemctl enable "$SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"

    log_info "System service installed and started successfully"
    log_info "To view logs: journalctl -u $SERVICE_NAME -f"
}

# Function to set up user service
setup_user_service() {
    local USER_SERVICE_DIR="$HOME/.config/systemd/user"
    local SERVICE_FILE="$USER_SERVICE_DIR/${SERVICE_NAME}.service"

    # Create user systemd directory
    mkdir -p "$USER_SERVICE_DIR"

    # Create user service file based on our working template
    log_info "Creating user service file at $SERVICE_FILE..."
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=EVOSEAL Evolution Service with Auto-Update
After=network.target
StartLimitIntervalSec=500
StartLimitBurst=5

[Service]
Type=simple
# User mode service - no User/Group needed

# Working directory - using /tmp to avoid permission issues
WorkingDirectory=/tmp

# Environment file from the project root (optional)
EnvironmentFile=-$EVOSEAL_ROOT/.env

# Set up environment variables
Environment="PYTHONPATH=$EVOSEAL_ROOT:$EVOSEAL_ROOT/SEAL"
Environment="EVOSEAL_ROOT=$EVOSEAL_ROOT"
Environment="EVOSEAL_VENV=$EVOSEAL_VENV"
Environment="EVOSEAL_LOGS=$EVOSEAL_LOGS"
Environment="EVOSEAL_USER_HOME=$HOME"

# Update and run script (runs at service start and then periodically)
ExecStart=/bin/bash -c 'source $HOME/.profile && $EVOSEAL_ROOT/scripts/evoseal-unified-runner.sh --mode=service'

# Restart configuration
Restart=always
RestartSec=5s

# Logging
StandardOutput=append:$EVOSEAL_LOGS/evoseal.log
StandardError=append:$EVOSEAL_LOGS/evoseal-error.log

# Minimal security settings for user service
NoNewPrivileges=true

[Install]
WantedBy=default.target
EOF

    # Ensure log directory exists
    mkdir -p "$EVOSEAL_LOGS"

    # Reload user systemd
    systemctl --user daemon-reload

    # Enable and start the user service
    systemctl --user enable "$SERVICE_NAME"
    systemctl --user restart "$SERVICE_NAME"

    # Enable linger for the user so service starts at boot
    if command -v loginctl >/dev/null 2>&1; then
        loginctl enable-linger "$SCRIPT_USER" || log_warn "Could not enable linger"
    fi

    log_info "User service installed and started successfully"
    log_info "To view logs: journalctl --user -u $SERVICE_NAME -f"
    log_info "To check status: systemctl --user status $SERVICE_NAME"
}

# Main execution
log_info "Starting EVOSEAL service installation in $INSTALL_MODE mode..."
log_info "Installation directory: $EVOSEAL_DIR"
log_info "Current user: $SCRIPT_USER"

install_dependencies
setup_service

log_success "EVOSEAL $INSTALL_MODE service installation completed successfully!"

if [ "$INSTALL_MODE" = "system" ]; then
    log_info "System service commands:"
    log_info "  Status: systemctl status $SERVICE_NAME"
    log_info "  Logs:   journalctl -u $SERVICE_NAME -f"
    log_info "  Stop:   sudo systemctl stop $SERVICE_NAME"
    log_info "  Start:  sudo systemctl start $SERVICE_NAME"
else
    log_info "User service commands:"
    log_info "  Status: systemctl --user status $SERVICE_NAME"
    log_info "  Logs:   journalctl --user -u $SERVICE_NAME -f"
    log_info "  Stop:   systemctl --user stop $SERVICE_NAME"
    log_info "  Start:  systemctl --user start $SERVICE_NAME"
    log_info "  Test:   $EVOSEAL_DIR/scripts/test_service_autoupdate.sh"
fi
