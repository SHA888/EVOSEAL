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
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")

# Ensure metrics directory exists
mkdir -p "$METRICS_DIR"

# Get git information
COMMIT_HASH=$(git rev-parse --short HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Get commit messages since last tag
COMMIT_MESSAGES=$(git log --pretty=format:"%s" "$LAST_TAG..HEAD" 2>/dev/null || git log --pretty=format:"%s" -n 10)

# Categorize commits
FEATURES=$(echo "$COMMIT_MESSAGES" | grep -iE '^(feat|add|new)' | sed 's/^/\n- /' | tr '\n' ' ')
FIXES=$(echo "$COMMIT_MESSAGES" | grep -iE '^(fix|bug|issue)' | sed 's/^/\n- /' | tr '\n' ' ')
PERF=$(echo "$COMMIT_MESSAGES" | grep -iE '^(perf|optimize)' | sed 's/^/\n- /' | tr '\n' ' ')
DOCS=$(echo "$COMMIT_MESSAGES" | grep -iE '^(docs|update readme)' | sed 's/^/\n- /' | tr '\n' ' ')

# Count changes
NUM_FEATURES=$(echo "$FEATURES" | grep -o '\- ' | wc -l || echo 0)
NUM_FIXES=$(echo "$FIXES" | grep -o '\- ' | wc -l || echo 0)
NUM_PERF=$(echo "$PERF" | grep -o '\- ' | wc -l || echo 0)

# Get code statistics
CHANGED_FILES=$(git diff --name-only "$LAST_TAG..HEAD" 2>/dev/null || git diff --name-only HEAD^ HEAD)
NUM_FILES_CHANGED=$(echo "$CHANGED_FILES" | wc -l)

# Count lines of code
ADDED_LINES=$(git diff --shortstat "$LAST_TAG..HEAD" 2>/dev/null | awk '{print $4}' || echo 0)
DELETED_LINES=$(git diff --shortstat "$LAST_TAG..HEAD" 2>/dev/null | awk '{print $6}' || echo 0)

# Get test coverage if available
if [ -f "coverage.xml" ]; then
    COVERAGE=$(grep -oP 'line-rate="\K[0-9.]+' coverage.xml | head -1)
else
    COVERAGE="0.0"
fi

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
    "code_size": {
      "added": $ADDED_LINES,
      "deleted": $DELETED_LINES,
      "files_changed": $NUM_FILES_CHANGED
    },
    "test_coverage": $COVERAGE,
    "changes": {
      "features": $NUM_FEATURES,
      "fixes": $NUM_FIXES,
      "performance": $NUM_PERF
    }
  },
  "performance": {
    "timestamp": "$TIMESTAMP",
    "memory_usage_mb": $(free -m | awk '/^Mem:/{print $3}'),
    "cpu_usage_percent": $(top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}')
  },
  "changes": {
    "features": [$FEATURES],
    "fixes": [$FIXES],
    "performance_improvements": [$PERF],
    "documentation_updates": [$DOCS]
  },
  "files_changed": [$(echo "$CHANGED_FILES" | sed 's/.*/"&"/' | paste -sd ',' -)]
}
EOL

# Also create a human-readable markdown file
MARKDOWN_FILE="$METRICS_DIR/release_notes_${VERSION}.md"
cat > "$MARKDOWN_FILE" <<EOL
# EVOSEAL $VERSION
Released on $(date -u '+%Y-%m-%d %H:%M:%S UTC')

## 📊 Metrics
- **Code Changes**: $ADDED_LINES lines added, $DELETED_LINES lines removed
- **Files Changed**: $NUM_FILES_CHANGED
- **Test Coverage**: $(echo "scale=2; $COVERAGE * 100" | bc)%

## ✨ New Features$FEATURES

## 🐛 Bug Fixes$FIXES

## ⚡ Performance Improvements$PERF

## 📚 Documentation Updates$DOCS

## 📝 Full Commit Log
$(git log --pretty=format:'- %s' "$LAST_TAG..HEAD" 2>/dev/null || echo "- No commits since last tag")
EOL

echo "Metrics collected and saved to $METRICS_FILE"
echo "Release notes generated at $MARKDOWN_FILE"
