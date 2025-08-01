# EVOSEAL systemd Service Integration

## Overview

EVOSEAL Phase 3 Bidirectional Continuous Evolution System is fully integrated with systemd as a user service, providing production-ready deployment with automatic startup, restart capabilities, and comprehensive logging.

## Service Configuration

### Service File Location
```
~/.config/systemd/user/evoseal.service
```

### Service Definition
```ini
[Unit]
Description=EVOSEAL Phase 3 Bidirectional Continuous Evolution Service
After=network.target
StartLimitIntervalSec=500
StartLimitBurst=5

[Service]
Type=simple

# Working directory - using /tmp to avoid permission issues
WorkingDirectory=/tmp

# Environment file from the project root (optional)
EnvironmentFile=-%h/EVOSEAL/.env

# Set up environment variables using systemd specifiers
Environment="PYTHONPATH=%h/EVOSEAL:%h/EVOSEAL/SEAL"
Environment="EVOSEAL_ROOT=%h/EVOSEAL"
Environment="EVOSEAL_VENV=%h/EVOSEAL/.venv"
Environment="EVOSEAL_LOGS=%h/EVOSEAL/logs"
Environment="EVOSEAL_USER_HOME=%h"

# Phase 3 Continuous Evolution System - Accessible via Tailscale
# Use %h for home directory and dynamic Tailscale IP detection
ExecStart=/bin/bash -c 'source %h/.profile && cd %h/EVOSEAL && TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "localhost") && python3 scripts/run_phase3_continuous_evolution.py --host="$TAILSCALE_IP" --port=9613 --verbose'

# Restart configuration
Restart=always
RestartSec=5s

# Logging
StandardOutput=append:%h/EVOSEAL/logs/evoseal.log
StandardError=append:%h/EVOSEAL/logs/evoseal-error.log

# Minimal security settings for user service
NoNewPrivileges=true

[Install]
WantedBy=default.target
```

### Portable Configuration Features

#### systemd Specifiers Used
- **`%h`**: User's home directory (replaces hardcoded `/home/username`)
- **Dynamic IP Detection**: Automatically detects Tailscale IP or falls back to localhost
- **Portable Paths**: All paths use `%h` for cross-user compatibility

#### Key Benefits
- ✅ **User Agnostic**: Works for any username/home directory
- ✅ **Machine Portable**: No hardcoded paths or IPs
- ✅ **Tailscale Auto-Detection**: Automatically finds Tailscale IP if available
- ✅ **Graceful Fallback**: Falls back to localhost if Tailscale unavailable

## Installation and Setup
StandardOutput=append:/home/kade/EVOSEAL/logs/evoseal.log
StandardError=append:/home/kade/EVOSEAL/logs/evoseal-error.log

# Minimal security settings for user service
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

## Service Management

### Basic Commands

```bash
# Check service status
systemctl --user status evoseal.service

# Start the service
systemctl --user start evoseal.service

# Stop the service
systemctl --user stop evoseal.service

# Restart the service
systemctl --user restart evoseal.service

# Enable auto-start on boot
systemctl --user enable evoseal.service

# Disable auto-start
systemctl --user disable evoseal.service
```

### Advanced Management

```bash
# Reload systemd configuration after editing service file
systemctl --user daemon-reload

# View service logs
journalctl --user -u evoseal.service

# Follow logs in real-time
journalctl --user -fu evoseal.service

# View logs with specific time range
journalctl --user -u evoseal.service --since "1 hour ago"

# View only error logs
journalctl --user -u evoseal.service --priority=err
```

## Service Features

### Automatic Startup
- **User Linger**: Enabled to start service on boot without user login
- **Auto-enable**: Service is enabled by default
- **Network Dependency**: Waits for network to be available

### Restart Behavior
- **Restart Policy**: Always restart on failure
- **Restart Delay**: 5 seconds between restart attempts
- **Start Limit**: Maximum 5 restart attempts in 500 seconds
- **Failure Recovery**: Automatic recovery from crashes

### Logging
- **Standard Output**: Appended to `/home/kade/EVOSEAL/logs/evoseal.log`
- **Standard Error**: Appended to `/home/kade/EVOSEAL/logs/evoseal-error.log`
- **systemd Journal**: All logs also available via `journalctl`
- **Log Rotation**: Handled by systemd journal rotation

### Security
- **User Service**: Runs as user service, no root privileges
- **NoNewPrivileges**: Prevents privilege escalation
- **Working Directory**: Uses `/tmp` to avoid permission issues
- **Environment Isolation**: Controlled environment variables

## Monitoring

### Service Status
```bash
# Detailed status information
systemctl --user status evoseal.service

# Check if service is active
systemctl --user is-active evoseal.service

# Check if service is enabled
systemctl --user is-enabled evoseal.service

# List all user services
systemctl --user list-units --type=service
```

### Performance Monitoring
```bash
# View service resource usage
systemctl --user show evoseal.service --property=MainPID,MemoryCurrent,CPUUsageNSec

# Monitor resource usage in real-time
watch 'systemctl --user show evoseal.service --property=MainPID,MemoryCurrent,CPUUsageNSec'
```

### Log Analysis
```bash
# View recent logs
journalctl --user -u evoseal.service --lines=50

# Search logs for specific terms
journalctl --user -u evoseal.service | grep "ERROR"
journalctl --user -u evoseal.service | grep "Phase 3"

# Export logs to file
journalctl --user -u evoseal.service > evoseal_service_logs.txt
```

## Integration with Phase 3

### Dashboard Access
When the service is running, the monitoring dashboard is available at:
- **URL**: http://localhost:9613
- **Features**: Real-time monitoring, WebSocket updates, system metrics
- **Access**: Local access only for security

### Service Components
The systemd service runs the complete Phase 3 system:
- **ContinuousEvolutionService**: Main orchestration service
- **MonitoringDashboard**: Real-time web dashboard
- **BidirectionalEvolutionManager**: EVOSEAL ↔ Devstral coordination
- **Health Monitoring**: Continuous system health checks

### Configuration
Service configuration can be customized by editing the service file:
```bash
# Edit service configuration
systemctl --user edit evoseal.service

# Or edit the main service file
nano ~/.config/systemd/user/evoseal.service

# Reload after changes
systemctl --user daemon-reload
systemctl --user restart evoseal.service
```

## Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check service status for errors
systemctl --user status evoseal.service

# View detailed logs
journalctl --user -xeu evoseal.service

# Check if dependencies are available
python3 scripts/run_phase3_continuous_evolution.py --health-check
```

#### Service Keeps Restarting
```bash
# Check error logs
journalctl --user -u evoseal.service --priority=err

# Check if port is already in use
netstat -tlnp | grep :9613

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

#### Permission Issues
```bash
# Check file permissions
ls -la ~/.config/systemd/user/evoseal.service

# Verify log directory permissions
ls -la /home/kade/EVOSEAL/logs/

# Check user linger status
loginctl show-user $USER | grep Linger
```

### Diagnostic Commands

```bash
# Complete service diagnostic
systemctl --user status evoseal.service
journalctl --user -u evoseal.service --lines=20
python3 scripts/run_phase3_continuous_evolution.py --health-check

# Check systemd user session
systemctl --user status

# Verify user linger
loginctl user-status $USER
```

## Maintenance

### Service Updates
When updating EVOSEAL code:
```bash
# Stop service
systemctl --user stop evoseal.service

# Update code (git pull, etc.)
cd /home/kade/EVOSEAL
git pull

# Restart service
systemctl --user start evoseal.service

# Verify service is running
systemctl --user status evoseal.service
```

### Log Management
```bash
# View log sizes
du -sh /home/kade/EVOSEAL/logs/

# Clean old logs (if needed)
find /home/kade/EVOSEAL/logs/ -name "*.log" -mtime +30 -delete

# Rotate systemd journal logs
sudo journalctl --vacuum-time=30d
```

### Backup Configuration
```bash
# Backup service configuration
cp ~/.config/systemd/user/evoseal.service ~/evoseal.service.backup

# Backup environment file
cp /home/kade/EVOSEAL/.env ~/evoseal.env.backup
```

## Migration from Legacy Service

The Phase 3 service replaces the legacy `evoseal-unified-runner.sh` script:

### Changes Made
- **Old**: `ExecStart=.../evoseal-unified-runner.sh --mode=service`
- **New**: `ExecStart=...python3 scripts/run_phase3_continuous_evolution.py --port=9613 --verbose`
- **Description**: Updated to "EVOSEAL Phase 3 Bidirectional Continuous Evolution Service"
- **Port**: Changed from 8081 to 9613 to avoid conflicts

### Migration Benefits
- **Real-time Dashboard**: Live monitoring with WebSocket updates
- **Bidirectional Evolution**: EVOSEAL ↔ Devstral improvement loop
- **Advanced Monitoring**: Comprehensive metrics and analytics
- **Better Error Handling**: Graceful error recovery and reporting
- **Modern Architecture**: Async/await throughout for better performance

## Best Practices

### Service Management
1. Always use `systemctl --user` commands (not root)
2. Check service status before making changes
3. Use `daemon-reload` after editing service files
4. Monitor logs regularly for issues
5. Keep service configuration backed up

### Monitoring
1. Set up log rotation to prevent disk space issues
2. Monitor resource usage periodically
3. Check dashboard regularly for system health
4. Set up alerts for service failures (optional)

### Security
1. Keep service running as user (not root)
2. Regularly update dependencies
3. Monitor for security vulnerabilities
4. Restrict dashboard access to localhost only

## Conclusion

The systemd integration provides a robust, production-ready deployment solution for EVOSEAL Phase 3. The service automatically starts on boot, recovers from failures, and provides comprehensive logging and monitoring capabilities. Combined with the real-time dashboard, this creates a complete continuous evolution system that operates reliably in production environments.
