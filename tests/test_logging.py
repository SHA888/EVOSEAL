"""
Tests for the EVOSEAL logging module.
"""

import json
import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module to test
from evoseal.utils.logging import (
    ContextFilter,
    JsonFormatter,
    LoggingMixin,
    PerformanceFilter,
    log_execution_time,
    setup_logging,
    with_request_id,
)


@pytest.fixture
def log_record():
    """Create a log record factory for testing with proper attribute handling."""

    def _create_log_record():
        # Create a custom LogRecord class that allows setting arbitrary attributes
        class CustomLogRecord(logging.LogRecord):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Initialize with None to allow attribute setting
                self.context = None
                self.request_id = None

        # Create the record using our custom class
        return CustomLogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

    # Return the factory function, not the record itself
    return _create_log_record


def test_json_formatter_format(log_record):
    """Test JSON formatting of log records."""
    # Get a fresh log record
    record = log_record()

    # Set the function name to a known value for testing
    record.funcName = "test_function"

    formatter = JsonFormatter()
    result = formatter.format(record)
    data = json.loads(result)

    # Check required fields
    assert "timestamp" in data
    assert data["level"] == "INFO"
    assert data["logger"] == "test"
    assert data["message"] == "Test message"
    assert data["module"] == "test_logging"
    assert data["function"] == "test_function"  # Should use the value we set
    assert data["line"] == 42
    assert "hostname" in data


@pytest.fixture
def context_filter():
    """Create a ContextFilter instance for testing."""
    return ContextFilter()


@patch('evoseal.utils.logging.context_filter')
def test_context_filter_with_no_context(mock_global_filter, log_record, context_filter):
    """Test filtering with no context."""
    # Set up the global filter mock to return our test filter
    mock_global_filter.return_value = context_filter

    # Create a fresh record for this test
    record = log_record()

    # Test with no context set
    assert context_filter.filter(record) is True
    # The filter should set request_id to "global" by default
    assert hasattr(record, "request_id")
    assert record.request_id == "global"
    # The filter should also set hostname
    assert hasattr(record, "hostname")


def test_context_filter_with_context(log_record, context_filter):
    """Test filtering with context."""
    # Create a fresh record for this test
    record = log_record()

    # Set context and test
    context = {"key": "value", "user_id": "test_user"}
    context_filter.set_context(context)
    assert context_filter.filter(record) is True

    # Check that context keys are set as attributes on the log record
    assert hasattr(record, "key")
    assert record.key == "value"
    assert hasattr(record, "user_id")
    assert record.user_id == "test_user"

    # Clear context for next test
    context_filter.set_context({})


def test_context_filter_with_nested_context(log_record, context_filter):
    """Test filtering with nested context."""
    # Test first level of context
    context_filter.set_context({"key1": "value1"})
    record1 = log_record()
    assert context_filter.filter(record1) is True
    assert hasattr(record1, "key1")
    assert record1.key1 == "value1"

    # Test second level of context and request ID with a fresh record
    context_filter.set_context({"key2": "value2"})
    context_filter.set_request_id("req123")
    record2 = log_record()
    assert context_filter.filter(record2) is True

    # Check that the second record has the updated context and request ID
    assert not hasattr(record2, "key1")  # Should not have the first context key
    assert hasattr(record2, "key2")
    assert record2.key2 == "value2"
    assert hasattr(record2, "request_id")
    assert record2.request_id == "req123"

    # Clear context and request ID for other tests
    context_filter.set_context({})
    context_filter.set_request_id(None)


def test_context_filter_with_request_id(log_record, context_filter):
    """Test setting request ID."""
    # Test with no request ID set (should default to "global")
    record1 = log_record()
    assert context_filter.filter(record1) is True
    assert hasattr(record1, "request_id")
    assert record1.request_id == "global"

    # Test with request ID set on a fresh record
    context_filter.set_request_id("test-request")
    record2 = log_record()
    assert context_filter.filter(record2) is True
    assert hasattr(record2, "request_id")
    assert record2.request_id == "test-request"

    # Clear request ID for other tests
    context_filter.set_request_id(None)


@pytest.fixture
def performance_filter():
    """Create a PerformanceFilter instance for testing."""
    return PerformanceFilter()


def test_performance_filter_with_non_perf_record(log_record, performance_filter):
    """Test filtering with non-performance record."""
    # Get a fresh log record
    record = log_record()
    # PerformanceFilter should return False for non-performance records
    assert performance_filter.filter(record) is False
    assert not hasattr(log_record, "is_performance")


def test_performance_filter_with_perf_record(log_record, performance_filter):
    """Test filtering with performance record."""
    setattr(log_record, "is_performance", True)
    assert performance_filter.filter(log_record) is False
    assert hasattr(log_record, "is_performance")


@pytest.fixture
def test_class():
    """Create a test class that uses LoggingMixin."""

    class TestClass(LoggingMixin):
        pass

    return TestClass()


def test_logging_mixin_initialization(test_class):
    """Test logger initialization in mixin."""
    assert hasattr(test_class, "logger")
    assert isinstance(test_class.logger, logging.Logger)
    # The logger name should be the full module path plus the class name
    assert test_class.logger.name == "tests.test_logging.TestClass"


def test_log_performance(test_class, mocker):
    """Test performance logging."""
    mock_logger = mocker.patch.object(test_class.__class__, "logger")

    # Call the method being tested with the correct signature
    test_class.log_performance("test_metric", 42, key="value")

    # Check that the logger was called with the expected arguments
    mock_logger.info.assert_called_once()
    args, kwargs = mock_logger.info.call_args
    assert "test_metric" in args[0]  # Check metric name is in message
    assert "42" in args[0]  # Check value is in message
    # Check extra context is properly set
    assert kwargs["extra"]["performance_metric"] == "test_metric"
    assert kwargs["extra"]["metric_value"] == 42
    assert kwargs["extra"]["key"] == "value"


@pytest.fixture
def temp_logging_config():
    """Create a temporary logging config file for testing."""
    temp_dir = tempfile.mkdtemp()
    config_file = os.path.join(temp_dir, "logging_config.json")

    # Default config for testing
    default_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"class": "evoseal.utils.logging.JsonFormatter"},
            "simple": {"format": "%(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "level": "INFO",
            },
            "file": {
                "class": "logging.FileHandler",
                "filename": os.path.join(temp_dir, "test.log"),
                "formatter": "json",
                "level": "DEBUG",
            },
        },
        "root": {"level": "DEBUG", "handlers": ["console", "file"]},
    }

    # Write the config file
    with open(config_file, "w") as f:
        json.dump(default_config, f)

    yield config_file, temp_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_setup_logging_with_config(temp_logging_config, mocker):
    """Test setting up logging with a config file."""
    config_file, temp_dir = temp_logging_config

    # Patch yaml.safe_load to return our test config
    test_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"class": "evoseal.utils.logging.JsonFormatter"},
            "simple": {"format": "%(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "level": "INFO",
            },
            "file": {
                "class": "logging.FileHandler",
                "filename": os.path.join(temp_dir, "test.log"),
                "formatter": "json",
                "level": "DEBUG",
            },
        },
        "root": {"level": "DEBUG", "handlers": ["console", "file"]},
    }

    # Mock the file operations
    mock_file = mocker.mock_open(read_data=yaml.dump(test_config))

    with (
        patch('builtins.open', mock_file),
        patch('yaml.safe_load', return_value=test_config) as mock_load,
        patch('logging.config.dictConfig') as mock_dict_config,
    ):

        # Setup logging
        logger = setup_logging(config_path=config_file)

        # Verify the logger was configured
        assert isinstance(logger, logging.Logger)

        # Verify dictConfig was called with our config
        mock_dict_config.assert_called_once()
        assert mock_dict_config.call_args[0][0] == test_config

        # Verify the returned logger is the 'evoseal' logger
        assert logger.name == "evoseal"

        # Verify the dictConfig was called with the expected file handler config
        config = mock_dict_config.call_args[0][0]
        assert 'handlers' in config
        assert 'file' in config['handlers']
        assert config['handlers']['file'].get('filename') == os.path.join(temp_dir, "test.log")


def test_setup_logging_default(mocker):
    """Test setting up logging with default config."""
    mock_dict_config = mocker.patch("logging.config.dictConfig")
    mock_open = mocker.mock_open()

    # Mock file operations to simulate config file not found
    mocker.patch('builtins.open', mock_open, create=True)
    mocker.patch('os.path.exists', return_value=False)

    # Setup logging with default config (should fall back to basic config)
    with patch('logging.basicConfig') as mock_basic_config:
        logger = setup_logging()

        # Verify basicConfig was called (fallback behavior)
        mock_basic_config.assert_called_once()

        # Verify the logger is returned and has the expected name
        assert isinstance(logger, logging.Logger)
        assert logger.name == "evoseal"


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return MagicMock()


def test_log_execution_time(mock_logger, mocker):
    """Test the log_execution_time decorator."""
    # Patch time.monotonic to return 0 on first call, 1.5 on second call
    mocker.patch("time.monotonic", side_effect=[0, 1.5])

    # Define a test function to decorate
    @log_execution_time(mock_logger)
    def test_func():
        return "result"

    # Call the decorated function
    result = test_func()

    # Verify the result is correct
    assert result == "result"

    # Verify the logger was called with the expected arguments
    mock_logger.debug.assert_called_once()
    args, kwargs = mock_logger.debug.call_args
    assert "extra" in kwargs
    assert "execution_time" in kwargs["extra"]
    assert kwargs["extra"]["execution_time"] == 1.5


def test_with_request_id(mock_logger, mocker):
    """Test the with_request_id decorator."""
    # Patch uuid.uuid4 to return a fixed value
    mocker.patch("uuid.uuid4", return_value="test-uuid-123")

    # Define a test function to decorate
    @with_request_id(mock_logger)
    def test_func():
        return "result"

    # Call the decorated function
    result = test_func()

    # Verify the result is correct
    assert result == "result"

    # Verify the logger was called with the expected arguments
    assert mock_logger.info.call_count == 2  # Start and end logs
    mock_logger.info.assert_any_call(
        "Starting request test-uuid-123", extra={"request_id": "test-uuid-123"}
    )
    mock_logger.info.assert_any_call(
        "Completed request test-uuid-123", extra={"request_id": "test-uuid-123"}
    )


# Remove the unittest.main() call as we're using pytest
