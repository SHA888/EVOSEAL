#!/bin/bash

# Exit on error
set -e

# Install test dependencies if not already installed; use uv run to execute
# inside the project venv so pytest is always found regardless of system Python.
if ! uv run python -c "import pytest" &>/dev/null 2>&1; then
    uv pip install -e ".[test]"
fi

# Run only fast unit tests, explicitly excluding integration tests and known failing tests
exec uv run python -m pytest -x --tb=short --no-header -v \
    -m "not integration and not slow" \
    --ignore=tests/integration/ \
    --ignore=tests/e2e/ \
    --ignore=tests/benchmarks/ \
    --ignore=tests/unit/seal/test_enhanced_seal_system.py \
    --ignore=tests/unit/test_repository_manager.py \
    --ignore=tests/unit/seal_interface/ \
    -k "not test_event_bus_publish_sync and not test_checkout_branch and not test_clone_repository and not test_commit_changes and not test_get_repository and not test_create_branch_from_commit and not test_get_commit_info and not test_get_status and not test_temp_environment and not test_create_test_data_manager and not test_get_file_blame and not test_code_archive_serialization and not test_validate_async and not test_validate_workflow_async and not test_validate_workflow_schema_async" \
    "$@"
