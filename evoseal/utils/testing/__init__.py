"""
Testing utilities for EVOSEAL.

This module provides tools for setting up and managing test environments,
including temporary directories, environment variables, and test data.
"""

from .environment import (
    TestEnvironment,
    TestDataManager,
    create_test_data_manager,
    temp_dir,
    temp_environment,
    temp_env_vars,
    temp_file,
)

__all__ = [
    'TestEnvironment',
    'TestDataManager',
    'create_test_data_manager',
    'temp_dir',
    'temp_environment',
    'temp_env_vars',
    'temp_file',
]
