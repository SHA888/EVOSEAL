#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/app"
cd "$APP_DIR"

# Load environment file if present
if [ -f "$APP_DIR/.evoseal.env" ]; then
  echo "Loading env from $APP_DIR/.evoseal.env"
  set -o allexport
  # shellcheck disable=SC1091
  source "$APP_DIR/.evoseal.env"
  set +o allexport
fi

# Ensure runtime dirs
mkdir -p "$APP_DIR/checkpoints" "$APP_DIR/data" "$APP_DIR/reports"

HOST="${EV_DASHBOARD_HOST:-0.0.0.0}"
PORT="${EV_DASHBOARD_PORT:-9613}"

# Allow overriding command
if [ "${1:-}" = "bash" ] || [ "${1:-}" = "sh" ]; then
  exec "$@"
fi

# Start Phase 3 continuous evolution system
exec python -u scripts/lib/evolution/run_phase3_continuous_evolution.py \
  --host "$HOST" \
  --port "$PORT" \
  "$@"
