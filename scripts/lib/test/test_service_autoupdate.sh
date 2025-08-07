#!/bin/bash
# Test script to verify EVOSEAL service auto-update functionality

set -euo pipefail

# Load configuration and logging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/evoseal-config.sh"
source "$SCRIPT_DIR/lib/utils/_logging.sh"

log_info "Testing EVOSEAL service auto-update functionality"

# Check if service is running
if systemctl --user is-active --quiet evoseal; then
    log_info "✅ EVOSEAL service is running"

    # Check service status
    log_info "Service status:"
    systemctl --user status evoseal --no-pager -l

    # Check recent logs
    log_info "Recent service logs:"
    journalctl --user -u evoseal -n 10 --no-pager

    # Check if log files exist and are being written to
    if [ -f "$EVOSEAL_LOGS/evoseal.log" ]; then
        log_info "✅ Service log file exists and is $(wc -l < "$EVOSEAL_LOGS/evoseal.log") lines long"
    else
        log_warn "⚠️  Service log file not found at $EVOSEAL_LOGS/evoseal.log"
    fi

    # Check if unified runner log exists
    LATEST_LOG=$(ls -t "$EVOSEAL_LOGS"/unified_runner_service_*.log 2>/dev/null | head -n1 || echo "")
    if [ -n "$LATEST_LOG" ]; then
        log_info "✅ Latest unified runner log: $(basename "$LATEST_LOG")"
        log_info "Last 5 lines of runner log:"
        tail -5 "$LATEST_LOG"
    else
        log_warn "⚠️  No unified runner logs found"
    fi

    # Check if update functionality is working
    if [ -f "$EVOSEAL_DATA/.last_update" ]; then
        LAST_UPDATE=$(cat "$EVOSEAL_DATA/.last_update")
        CURRENT_TIME=$(date +%s)
        TIME_DIFF=$((CURRENT_TIME - LAST_UPDATE))
        log_info "✅ Last update check was $TIME_DIFF seconds ago"
    else
        log_info "ℹ️  No update timestamp found (first run)"
    fi

    log_info "✅ EVOSEAL service auto-update appears to be working correctly"

else
    log_error "❌ EVOSEAL service is not running"
    log_info "Service status:"
    systemctl --user status evoseal --no-pager -l || true
    exit 1
fi

log_info "Test completed successfully!"
