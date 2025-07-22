#!/bin/bash
#
# EVOSEAL Metrics Collection Script
# Collects metrics after each evolution cycle and stores them in the metrics directory
#
# Usage: ./collect_metrics.sh <version> <improvement_metrics>

set -e

# Configuration
METRICS_DIR="${EVOSEAL_METRICS_DIR:-./metrics}"
VERSION=$1
IMPROVEMENT_METRICS=${2:-0}
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Ensure metrics directory exists
mkdir -p "$METRICS_DIR"

# Get current git commit hash
COMMIT_HASH=$(git rev-parse --short HEAD)

# Get current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Get list of changed files
CHANGED_FILES=$(git diff --name-only HEAD^ HEAD 2>/dev/null || echo "")

# Count lines of code (simple count)
TOTAL_LINES=$(find . -type f -name '*.py' -o -name '*.sh' | xargs wc -l | tail -n 1 | awk '{print $1}')

# Create metrics file
METRICS_FILE="$METRICS_DIR/evolution_${VERSION}_${TIMESTAMP//[: -]/_}.json"

# Generate metrics
cat > "$METRICS_FILE" <<EOL
{
  "version": "$VERSION",
  "timestamp": "$TIMESTAMP",
  "commit": "$COMMIT_HASH",
  "branch": "$BRANCH",
  "metrics": {
    "iterations": 1,
    "improvements": $([ "$IMPROVEMENT_METRICS" -gt 0 ] && echo 1 || echo 0),
    "regressions": $([ "$IMPROVEMENT_METRICS" -lt 0 ] && echo 1 || echo 0),
    "code_size": $TOTAL_LINES,
    "changed_files": [$(echo "$CHANGED_FILES" | sed 's/.*/"&"/' | paste -sd ',' -)]
  },
  "performance": {
    "timestamp": "$TIMESTAMP",
    "memory_usage": $(free -m | awk '/^Mem:/{print $3}'),
    "cpu_usage": $(top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}')
  },
  "new_features": [
    $(git log --pretty=format:'%s' HEAD^..HEAD | grep -i '^feat\|^add\|^new' | sed 's/.*/"&"/' | sort -u | paste -sd ',' -)
  ],
  "bug_fixes": [
    $(git log --pretty=format:'%s' HEAD^..HEAD | grep -i '^fix\|^bug\|^issue' | sed 's/.*/"&"/' | sort -u | paste -sd ',' -)
  ]
}
EOL

echo "Metrics collected and saved to $METRICS_FILE"
