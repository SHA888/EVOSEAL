# Deployment Guide

This guide provides instructions for deploying EVOSEAL in various environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Serverless Deployment](#serverless-deployment)
- [Configuration Management](#configuration-management)
- [Scaling](#scaling)
- [Monitoring](#monitoring)
- [Backup and Recovery](#backup-and-recovery)
- [Security Considerations](#security-considerations)

## Prerequisites

- Python 3.10+
- pip (Python package manager)
- Git
- (Optional) Docker and Docker Compose
- (Optional) Kubernetes cluster (for production)

## Systemd Service Setup

EVOSEAL can be run as a systemd service for continuous operation. Recommended: user-mode service (no sudo), which integrates with your user session and journald.

### 1. Create Environment File

Copy the template environment file to your home and customize it if needed:

```bash
cp .evoseal.env.template ~/.evoseal.env
# Edit ~/.evoseal.env to customize settings
```

### 2. Install the Service (User Mode - Recommended)

Copy the service template into your user systemd directory and enable lingering to start at boot:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/evoseal.service.template ~/.config/systemd/user/evoseal.service

# Allow user services to start at boot (one-time)
loginctl enable-linger "$USER"

# Reload user systemd
systemctl --user daemon-reload

# Enable and start the service
systemctl --user enable --now evoseal.service
```

### 3. Verify Service Status

Check if the service is running:

```bash
systemctl --user status evoseal.service
```

### 4. View Logs

To view the logs (journald):

```bash
# Follow logs in real-time
journalctl --user-unit evoseal.service -f

# View full logs
journalctl --user-unit evoseal.service --no-pager
```

### Optional: System-wide Service (root)

If you need a system-wide service, copy the template to `/etc/systemd/system/` and use `sudo`:

```bash
sudo cp systemd/evoseal.service.template /etc/systemd/system/evoseal.service
sudo systemctl daemon-reload
sudo systemctl enable --now evoseal.service
sudo systemctl status evoseal.service
sudo journalctl -u evoseal.service -f
```

## Operations Runbook (systemd)

- **Start/Stop/Restart**

  ```bash
  systemctl --user start evoseal.service
  systemctl --user stop evoseal.service
  systemctl --user restart evoseal.service
  systemctl --user status evoseal.service
  ```

- **Logs**

  ```bash
  journalctl --user-unit evoseal.service -f
  journalctl --user-unit evoseal.service --since "-1h"
  ```

- **Update config/env**

  ```bash
  # After editing ~/.evoseal.env or updating code
  systemctl --user daemon-reload
  systemctl --user restart evoseal.service
  ```

- **Enable on boot**

  ```bash
  loginctl enable-linger "$USER"
  ```

- **Health watchdog (optional)**

  Install a periodic watchdog to ensure the service is running:

  ```bash
  chmod +x scripts/evoseal_watchdog.sh
  cp systemd/evoseal-watchdog.service ~/.config/systemd/user/
  cp systemd/evoseal-watchdog.timer ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user enable --now evoseal-watchdog.timer
  systemctl --user list-timers | grep evoseal
  ```

  Optional: set an HTTP health endpoint in your env file to enable HTTP checks (otherwise only service state is checked):

  ```ini
  # In ~/.evoseal.env
  HEALTH_URL=http://127.0.0.1:9613/health
  ```

## Systemd Smoke Test

Run a quick verification after enabling the service:

```bash
chmod +x scripts/smoke_test_systemd.sh
scripts/smoke_test_systemd.sh
```

## Local Development

### 1. Clone the Repository

```bash
git clone https://github.com/SHA888/EVOSEAL.git
cd EVOSEAL
```

### 2. Set Up Virtual Environment

```bash
python -m venv venv
source .venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```ini
# Required
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Optional
LOG_LEVEL=INFO
CACHE_DIR=./.cache
```

### 5. Run the Application

```bash
python -m evoseal.cli
```

## Docker Deployment

### 1. Build the Docker Image

```bash
docker build -t evoseal:latest .
```

### 2. Run the Container

```bash
docker run -d \
  --name evoseal \
  -p 8000:8000 \
  --env-file .env \
  evoseal:latest
```

### 3. Using Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  evoseal:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./cache:/app/.cache
    restart: unless-stopped
```

Then run:

```bash
docker-compose up -d
```

## Kubernetes Deployment

### 1. Create a Namespace

```bash
kubectl create namespace evoseal
```

### 2. Create a Secret for Environment Variables

```bash
kubectl create secret generic evoseal-secrets \
  --namespace=evoseal \
  --from-env-file=.env
```

### 3. Deploy the Application

Create a `deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: evoseal
  namespace: evoseal
spec:
  replicas: 3
  selector:
    matchLabels:
      app: evoseal
  template:
    metadata:
      labels:
        app: evoseal
    spec:
      containers:
      - name: evoseal
        image: your-registry/evoseal:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: evoseal-secrets
        resources:
          limits:
            cpu: "1"
            memory: "1Gi"
          requests:
            cpu: "500m"
            memory: "512Mi"
```

### 4. Create a Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: evoseal
  namespace: evoseal
spec:
  selector:
    app: evoseal
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
```

### 5. Apply the Configuration

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

## Serverless Deployment

### AWS Lambda

1. Install the AWS SAM CLI
2. Create a `template.yaml`
3. Deploy using SAM

```bash
sam build
sam deploy --guided
```

## Configuration Management

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | Your OpenAI API key |
| `ANTHROPIC_API_KEY` | Yes | - | Your Anthropic API key |
| `LOG_LEVEL` | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `CACHE_DIR` | No | ./.cache | Directory to store cache files |

### Configuration Files

EVOSEAL supports configuration through YAML files. The default location is `config/config.yaml`.

## Scaling

### Horizontal Scaling

- Use Kubernetes HPA (Horizontal Pod Autoscaler)
- Set appropriate resource requests and limits
- Use a message queue for task distribution

### Caching

- Enable caching for API responses
- Use Redis or Memcached for distributed caching

## Monitoring

### Logging

- Configure log aggregation (ELK, Loki, etc.)
- Set up log rotation

### Metrics

- Expose Prometheus metrics
- Set up Grafana dashboards
- Monitor error rates and latency

### Alerting

- Set up alerts for errors and performance issues
- Use tools like Prometheus Alertmanager

## Backup and Recovery

### Data Backup

- Regularly back up your database
- Test restoration procedures
- Store backups in multiple locations

### Disaster Recovery

- Have a disaster recovery plan
- Test failover procedures
- Document recovery steps

## Security Considerations

### Network Security

- Use TLS/SSL for all communications
- Implement network policies
- Use a WAF (Web Application Firewall)

### Access Control

- Implement proper authentication and authorization
- Use role-based access control (RBAC)
- Rotate API keys regularly

### Data Protection

- Encrypt sensitive data at rest and in transit
- Implement proper key management
- Follow the principle of least privilege

## Upgrading

1. Check the release notes for breaking changes
2. Backup your data
3. Test the upgrade in a staging environment
4. Deploy to production during a maintenance window

## Troubleshooting

### Common Issues

1. **API Connection Issues**
   - Check your API keys
   - Verify network connectivity
   - Check rate limits

2. **Performance Problems**
   - Check resource utilization
   - Review query performance
   - Check for memory leaks

3. **Deployment Failures**
   - Check container logs
   - Verify configuration
   - Check resource quotas

## Support

For additional help, please [open an issue](https://github.com/SHA888/EVOSEAL/issues).
