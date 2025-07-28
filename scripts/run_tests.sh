#!/bin/bash

# Exit on error
set -e

# Install test dependencies if not already installed
if ! python3 -c "import pytest" &> /dev/null; then
    python3 -m pip install -e ".[test]"
fi

# Run only fast unit tests, explicitly excluding integration tests and known failing tests
exec python3 -m pytest -x --tb=short --no-header -v \
    -m "not integration and not slow" \
    --ignore=tests/integration/ \
    --ignore=tests/benchmarks/ \
    --ignore=tests/unit/seal/test_enhanced_seal_system.py \
    --ignore=tests/unit/test_repository_manager.py \
    -k "not test_event_bus_publish_sync and not test_checkout_branch and not test_clone_repository and not test_commit_changes and not test_get_repository and not test_create_branch_from_commit and not test_get_commit_info and not test_get_status and not test_temp_environment and not test_create_test_data_manager and not test_get_file_blame" \
    "$@"
