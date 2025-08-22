#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="evoseal.service"
USER_SYSTEMCTL="systemctl --user"
HEALTH_URL="${HEALTH_URL:-}"

info() { echo "[INFO] $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

info "Checking systemd user service: ${SERVICE_NAME}"

if $USER_SYSTEMCTL is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
  info "Service is enabled at boot."
else
  info "Service is NOT enabled at boot. You can enable with: systemctl --user enable --now ${SERVICE_NAME}"
fi

if $USER_SYSTEMCTL is-active --quiet "$SERVICE_NAME"; then
  info "Service is active."
else
  $USER_SYSTEMCTL status "$SERVICE_NAME" || true
  fail "Service is not active. Start it with: systemctl --user start ${SERVICE_NAME}"
fi

if [[ -n "$HEALTH_URL" ]]; then
  info "Performing HTTP health check: $HEALTH_URL"
  if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    info "Healthcheck passed."
  else
    $USER_SYSTEMCTL status "$SERVICE_NAME" || true
    fail "Healthcheck FAILED at $HEALTH_URL"
  fi
else
  info "HEALTH_URL not set. Skipping HTTP health check."
fi

info "Recent logs:"
journalctl --user-unit "$SERVICE_NAME" -n 20 --no-pager || true

info "Smoke test completed successfully."
