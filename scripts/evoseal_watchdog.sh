#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="evoseal.service"
USER_SYSTEMCTL="systemctl --user"
LOG_TAG="evoseal-watchdog"

# Optional HTTP health URL (set in ~/.evoseal.env as HEALTH_URL=http://host:port/health)
HEALTH_URL="${HEALTH_URL:-}"

log() {
  # Logs to journald and stdout
  local msg="$1"
  echo "[$(date -Is)] $msg"
  logger -t "$LOG_TAG" -- "$msg" || true
}

# Check if the user systemd is responsive
if ! $USER_SYSTEMCTL is-system-running >/dev/null 2>&1; then
  log "User systemd not fully running; continuing health check anyway."
fi

# 1) Check service active state
if ! $USER_SYSTEMCTL is-active --quiet "$SERVICE_NAME"; then
  log "Service $SERVICE_NAME is not active. Attempting restart."
  $USER_SYSTEMCTL restart "$SERVICE_NAME" || true
  exit 0
fi

# 2) Optional HTTP health check
if [[ -n "$HEALTH_URL" ]]; then
  if ! curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    log "Healthcheck failed for $HEALTH_URL. Restarting $SERVICE_NAME."
    $USER_SYSTEMCTL restart "$SERVICE_NAME" || true
    exit 0
  fi
fi

log "Health OK for $SERVICE_NAME${HEALTH_URL:+ (URL: $HEALTH_URL)}."
