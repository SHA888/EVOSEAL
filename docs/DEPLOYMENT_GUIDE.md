# EVOSEAL Phase 3 Deployment Guide

## Overview

This guide covers the complete deployment of EVOSEAL Phase 3 Bidirectional Continuous Evolution System, from initial setup to production operation with systemd integration.

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended)
- **Python**: 3.10 or higher
- **Memory**: 8GB RAM minimum (32GB recommended for GPU fine-tuning)
- **Storage**: 50GB free space (for models and evolution data)
- **Network**: Internet access for initial setup

### Hardware Requirements
- **CPU**: Multi-core processor (6+ cores recommended)
- **GPU**: Optional but recommended (RTX 4090 or equivalent for full fine-tuning)
- **Disk**: SSD recommended for better performance

## Installation

### Step 1: Clone Repository
```bash
git clone https://github.com/SHA888/EVOSEAL
cd EVOSEAL
```

### Step 2: Python Environment Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install core dependencies
pip install -r requirements.txt

# Install Phase 3 specific dependencies
pip install aiohttp aiohttp-cors pydantic-settings

# Install in development mode
pip install -e .
```

### Step 3: Ollama and Devstral Setup
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull Devstral model (14GB download)
ollama pull devstral:latest

# Start Ollama service
ollama serve &

# Verify installation
ollama list
curl http://localhost:11434/api/tags
```

### Step 4: Configuration
```bash
# Copy environment template (if exists)
cp .env.example .env

# Edit configuration as needed
nano .env
```

### Step 5: Health Check
```bash
# Run comprehensive health check
python3 scripts/run_phase3_continuous_evolution.py --health-check
```

## Deployment Options

### Option 1: Development/Testing Deployment

For development and testing purposes:

```bash
# Start Phase 3 system directly
python3 scripts/run_phase3_continuous_evolution.py --verbose

# Access dashboard
open http://localhost:8081
```

### Option 2: Production Deployment with systemd

For production environments (recommended):

#### Enable User Linger
```bash
# Enable user linger for auto-start on boot
sudo loginctl enable-linger $USER
```

#### Service Configuration
The systemd service is pre-configured at:
```
~/.config/systemd/user/evoseal.service
```

#### Start Production Service
```bash
# Reload systemd configuration
systemctl --user daemon-reload

# Enable and start service
systemctl --user enable evoseal.service
systemctl --user start evoseal.service

# Verify service status
systemctl --user status evoseal.service

# Access production dashboard
open http://localhost:8081
```

## Configuration

### Environment Variables

Key environment variables for Phase 3:

```bash
# EVOSEAL Core
export EVOSEAL_ROOT="/home/kade/EVOSEAL"
export EVOSEAL_LOGS="/home/kade/EVOSEAL/logs"
export PYTHONPATH="/home/kade/EVOSEAL:/home/kade/EVOSEAL/SEAL"

# Phase 3 Specific
export EVOSEAL_DASHBOARD_PORT="8081"
export EVOSEAL_EVOLUTION_INTERVAL="3600"  # 1 hour
export EVOSEAL_TRAINING_INTERVAL="1800"   # 30 minutes
export EVOSEAL_MIN_SAMPLES="50"

# Ollama Configuration
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="devstral:latest"
```

### Command Line Options

Phase 3 system supports extensive configuration:

```bash
python3 scripts/run_phase3_continuous_evolution.py \
  --port=8081 \                        # Dashboard port
  --evolution-interval=3600 \          # Evolution check interval (seconds)
  --training-interval=1800 \           # Training check interval (seconds)
  --min-samples=50 \                   # Minimum samples for training
  --verbose                            # Enable verbose logging
```

### systemd Service Configuration

Edit service configuration if needed:

```bash
# Edit service file
nano ~/.config/systemd/user/evoseal.service

# Key configuration sections:
# - ExecStart: Main command and arguments
# - Environment: Environment variables
# - Restart: Restart behavior
# - Logging: Log file locations

# Reload after changes
systemctl --user daemon-reload
systemctl --user restart evoseal.service
```

## Monitoring and Management

### Real-time Dashboard

Access the monitoring dashboard:
- **Development**: http://localhost:8081
- **Production**: http://localhost:8081

Dashboard features:
- Service status and uptime
- Evolution metrics and progress
- Training status and model versions
- Performance analytics
- Live activity log with WebSocket updates

### Service Management

```bash
# Check service status
systemctl --user status evoseal.service

# View real-time logs
journalctl --user -fu evoseal.service

# Restart service
systemctl --user restart evoseal.service

# Stop/start service
systemctl --user stop evoseal.service
systemctl --user start evoseal.service
```

### Log Management

Logs are written to multiple locations:

```bash
# Application logs
tail -f /home/kade/EVOSEAL/logs/phase3_continuous_evolution.log

# Service logs (stdout)
tail -f /home/kade/EVOSEAL/logs/evoseal.log

# Error logs (stderr)
tail -f /home/kade/EVOSEAL/logs/evoseal-error.log

# systemd journal
journalctl --user -fu evoseal.service
```

## Data Management

### Data Directories

Phase 3 creates several data directories:

```
data/continuous_evolution/
├── evolution_data/          # Phase 1: Evolution data collection
├── bidirectional/           # Phase 3: Bidirectional evolution data
│   ├── training/           # Training data and models
│   │   └── versions/       # Model versions
│   └── evolution_report_*.json  # Evolution reports
└── logs/                   # Application logs
```

### Backup Strategy

```bash
# Backup evolution data
tar -czf evoseal_data_backup_$(date +%Y%m%d).tar.gz data/

# Backup configuration
cp ~/.config/systemd/user/evoseal.service ~/evoseal_service_backup.service
cp .env ~/evoseal_env_backup.env

# Backup logs (optional)
tar -czf evoseal_logs_backup_$(date +%Y%m%d).tar.gz logs/
```

### Data Cleanup

```bash
# Clean old evolution reports (older than 30 days)
find data/continuous_evolution/bidirectional/ -name "evolution_report_*.json" -mtime +30 -delete

# Clean old model versions (keep last 10)
cd data/continuous_evolution/bidirectional/training/versions/
ls -t | tail -n +11 | xargs rm -rf

# Rotate logs
find logs/ -name "*.log" -mtime +7 -exec gzip {} \;
```

## Security

### Service Security

- **User Service**: Runs as user service, no root privileges required
- **NoNewPrivileges**: Prevents privilege escalation
- **Local Access**: Dashboard only accessible on localhost
- **Environment Isolation**: Controlled environment variables

### Network Security

- **Local Operation**: All processing local, no external API calls
- **Ollama Local**: Model inference entirely local
- **Dashboard Binding**: Dashboard only binds to localhost interface
- **No External Exposure**: No services exposed to external networks

### Data Security

- **Local Storage**: All data stored locally
- **File Permissions**: Proper file permissions on data directories
- **Log Rotation**: Automatic log rotation to prevent disk space issues

## Performance Optimization

### System Optimization

```bash
# Increase file descriptor limits
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Optimize Python performance
export PYTHONOPTIMIZE=1
export PYTHONDONTWRITEBYTECODE=1
```

### Resource Monitoring

```bash
# Monitor system resources
htop

# Monitor disk usage
df -h
du -sh data/

# Monitor memory usage
free -h

# Monitor service resource usage
systemctl --user show evoseal.service --property=MemoryCurrent,CPUUsageNSec
```

### Performance Tuning

```bash
# Adjust evolution intervals for performance
python3 scripts/run_phase3_continuous_evolution.py \
  --evolution-interval=7200 \    # Check every 2 hours
  --training-interval=3600 \     # Check training every hour
  --min-samples=100              # Require more samples before training
```

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Check what's using the port
netstat -tlnp | grep :8081

# Kill process using port
sudo fuser -k 8081/tcp

# Or use different port
python3 scripts/run_phase3_continuous_evolution.py --port=8082
```

#### Ollama Not Running
```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve &

# Check if Devstral is available
ollama list | grep devstral
```

#### Service Won't Start
```bash
# Check service status
systemctl --user status evoseal.service

# View detailed logs
journalctl --user -xeu evoseal.service

# Run health check
python3 scripts/run_phase3_continuous_evolution.py --health-check
```

#### Permission Issues
```bash
# Check file permissions
ls -la ~/.config/systemd/user/evoseal.service
ls -la /home/kade/EVOSEAL/logs/

# Fix permissions if needed
chmod 644 ~/.config/systemd/user/evoseal.service
chmod -R 755 /home/kade/EVOSEAL/logs/
```

### Diagnostic Commands

```bash
# Complete system diagnostic
echo "=== EVOSEAL Phase 3 Diagnostic ==="
echo "Service Status:"
systemctl --user status evoseal.service

echo -e "\nOllama Status:"
curl -s http://localhost:11434/api/tags | jq .

echo -e "\nDisk Usage:"
df -h /home/kade/EVOSEAL

echo -e "\nMemory Usage:"
free -h

echo -e "\nRecent Logs:"
journalctl --user -u evoseal.service --lines=10 --no-pager
```

## Maintenance

### Regular Maintenance Tasks

#### Daily
- Check service status
- Monitor dashboard for issues
- Review error logs

#### Weekly
- Check disk usage
- Review evolution progress
- Update system packages

#### Monthly
- Backup evolution data
- Clean old logs and reports
- Update EVOSEAL codebase
- Review performance metrics

### Update Procedure

```bash
# Stop service
systemctl --user stop evoseal.service

# Backup current state
tar -czf evoseal_backup_$(date +%Y%m%d).tar.gz data/ logs/ .env

# Update codebase
git pull origin main

# Update dependencies
pip install -r requirements.txt

# Run health check
python3 scripts/run_phase3_continuous_evolution.py --health-check

# Restart service
systemctl --user start evoseal.service

# Verify operation
systemctl --user status evoseal.service
```

## Scaling and High Availability

### Horizontal Scaling

For larger deployments:

```bash
# Run multiple instances on different ports
python3 scripts/run_phase3_continuous_evolution.py --port=8081 &
python3 scripts/run_phase3_continuous_evolution.py --port=8082 &

# Use load balancer (nginx example)
upstream evoseal_backend {
    server localhost:8081;
    server localhost:8082;
}
```

### High Availability Setup

```bash
# Set up multiple Ollama instances
ollama serve --port 11434 &
ollama serve --port 11435 &

# Configure provider fallback in EVOSEAL
# Edit configuration to include multiple Ollama endpoints
```

## Conclusion

This deployment guide provides comprehensive instructions for setting up EVOSEAL Phase 3 in both development and production environments. The systemd integration ensures reliable operation with automatic startup, restart capabilities, and comprehensive monitoring.

For additional support and troubleshooting, refer to:
- [Phase 3 Documentation](PHASE3_BIDIRECTIONAL_EVOLUTION.md)
- [systemd Integration Guide](SYSTEMD_INTEGRATION.md)
- [Main README](../README.md)

The Phase 3 system is designed for continuous operation and will automatically evolve and improve both EVOSEAL and Devstral through the bidirectional evolution loop.
