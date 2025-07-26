#!/bin/bash
# DEPRECATED: This script has been replaced by evoseal-unified-runner.sh
# 
# This file has been renamed to indicate it's deprecated.
# The functionality has been consolidated into evoseal-unified-runner.sh
#
# Migration:
#   Old: ./run_continuous.sh [iterations] [task_file]
#   New: ./evoseal-unified-runner.sh --mode=continuous --iterations=[iterations] --task-file=[task_file]
#
# The new unified runner provides:
# - Better error handling and logging
# - Multiple operation modes (service, continuous, auto)
# - Integration with the systemd service
# - Consistent configuration management
#
# This file will be removed in a future version.

echo "⚠️  DEPRECATED: run_continuous.sh has been replaced by evoseal-unified-runner.sh"
echo ""
echo "Please use the new unified runner instead:"
echo "  ./evoseal-unified-runner.sh --mode=continuous --help"
echo ""
echo "Migration example:"
echo "  Old: ./run_continuous.sh 5 ./tasks/my_task.json"
echo "  New: ./evoseal-unified-runner.sh --mode=continuous --iterations=5 --task-file=./tasks/my_task.json"
echo ""
exit 1
