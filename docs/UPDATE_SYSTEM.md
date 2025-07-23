# EVOSEAL Automatic Update System

This document describes the automatic update system for EVOSEAL, which ensures your installation stays up-to-date with the latest changes.

## Components

1. **Update Script**: `scripts/update_evoseal.sh`
   - Handles the update process
   - Can be run manually or automatically
   - Logs all activities to `logs/update_*.log`

2. **Configuration**: `scripts/evoseal-config.sh`
   - Centralized configuration
   - Defines all paths and settings
   - Can be overridden by environment variables or `.evoseal.local`

3. **Systemd Service**: `evoseal-update.service`
   - Manages the update process as a system service
   - Runs as the `kade` user

4. **Systemd Timer**: `evoseal-update.timer`
   - Triggers daily updates
   - Includes randomized delay to prevent thundering herd

## Configuration

### Environment Variables

You can customize the behavior by setting these environment variables:

- `EVOSEAL_HOME`: Base directory of the EVOSEAL installation
- `EVOSEAL_VENV`: Path to the Python virtual environment
- `EVOSEAL_LOGS`: Directory for log files
- `EVOSEAL_DATA`: Directory for data files
- `EVOSEAL_SERVICE_NAME`: Name of the EVOSEAL service

### Local Configuration

Create a `.evoseal.local` file in the EVOSEAL root directory to override default settings:

```bash
# Example .evoseal.local
EVOSEAL_HOME="/path/to/evoseal"
EVOSEAL_VENV="$EVOSEAL_HOME/.venv"
EVOSEAL_LOGS="/var/log/evoseal"
EVOSEAL_DATA="/var/lib/evoseal"
```

## Manual Update

To manually update EVOSEAL:

```bash
# Run the update script directly
./scripts/update_evoseal.sh

# Or use systemd
sudo systemctl start evoseal-update.service
```

## Logs

Update logs are stored in the `logs` directory with timestamps:

```
logs/update_YYYYMMDD_HHMMSS.log
```

## Troubleshooting

### Check Timer Status

```bash
systemctl list-timers | grep evoseal
```

### View Service Logs

```bash
journalctl -u evoseal-update.service -n 50 --no-pager
```

### Check Last Update

```bash
ls -l logs/update_*.log | tail -n 1
```

## Security Considerations

- The update script runs with the same permissions as the `kade` user
- Git operations use SSH keys from the `kade` user's home directory
- Logs contain sensitive information and should be secured
- The timer includes a randomized delay to prevent thundering herd
