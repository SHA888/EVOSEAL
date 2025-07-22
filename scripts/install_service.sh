#!/bin/bash
# Script to install the EVOSEAL systemd service

# Get the current directory
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Copy the service file to the systemd directory
echo "Copying service file to systemd directory..."
sudo cp "$SCRIPT_DIR/evoseal.service" /etc/systemd/system/

# Reload systemd to recognize the new service
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable the service to start on boot
echo "Enabling service to start on boot..."
sudo systemctl enable evoseal.service

echo "EVOSEAL service installed successfully!"
echo "To start the service now, run: sudo systemctl start evoseal.service"
echo "To check service status, run: sudo systemctl status evoseal.service"
echo "To view logs, run: journalctl -u evoseal.service -f"
