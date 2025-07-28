# EVOSEAL Continuous Operation

This guide explains how to run EVOSEAL continuously as a background service, ensuring it keeps operating even after system restarts.

## Quick Start

To start EVOSEAL immediately in the foreground:

```bash
cd /home/kade/EVOSEAL
source .venv/bin/activate
./scripts/run_continuous.sh
```

## Running as a Background Service

EVOSEAL can be run as a systemd service for true continuous operation:

1. Install the service:
   ```bash
   ./scripts/install_service.sh
   ```

2. Start the service:
   ```bash
   sudo systemctl start evoseal.service
   ```

3. Verify it's running:
   ```bash
   sudo systemctl status evoseal.service
   ```

## Monitoring

### Service Monitoring

- **Check service status**:
  ```bash
  sudo systemctl status evoseal.service
  ```

- **View logs**:
  ```bash
  journalctl -u evoseal.service -f
  ```

### CLI Monitoring

You can also monitor EVOSEAL using the CLI commands:

```bash
cd /home/kade/EVOSEAL
source .venv/bin/activate
evoseal 0.1.1 status
evoseal 0.1.1 pipeline status
```

### Log and Results Files

- Logs are stored in `/home/kade/EVOSEAL/logs/`
- Results are stored in `/home/kade/EVOSEAL/results/`

## Configuration

Edit the following files to customize continuous operation:

- **Service configuration**: `/home/kade/EVOSEAL/scripts/evoseal.service`
- **Runtime script**: `/home/kade/EVOSEAL/scripts/run_continuous.sh`
- **Default task**: `/home/kade/EVOSEAL/tasks/default_task.json`

## Stopping the Service

```bash
sudo systemctl stop evoseal.service
```

To disable it from starting at boot:
```bash
sudo systemctl disable evoseal.service
```

## Troubleshooting

If EVOSEAL is not running as expected:

1. Check the service status for error messages
2. Verify log files for specific errors
3. Ensure all required dependencies are installed
4. Check that the environment variables in `.env` are properly configured
5. Validate that the task file exists and has the correct format
