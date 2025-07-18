"""Unit tests for the error handling framework."""

import io
import logging
import sys
import time
import unittest
from datetime import datetime
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch

from evoseal.core.errors import (
    BaseError,
    ConfigurationError,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    IntegrationError,
    RetryableError,
    ValidationError,
    error_boundary,
    error_handler,
    retry_on_error,
)
from evoseal.utils.error_handling import (
    create_error_response,
    handle_errors,
    log_error,
    setup_logging,
)


class TestBaseError(unittest.TestCase):
    """Test cases for the BaseError class and its subclasses."""

    def test_base_error_creation(self) -> None:
        """Test creating a basic error with default values."""
        error = BaseError("Something went wrong")
        self.assertEqual(str(error), "UNKNOWN_ERROR: Something went wrong")
        self.assertEqual(error.code, "UNKNOWN_ERROR")
        self.assertEqual(error.category, ErrorCategory.UNKNOWN)
        self.assertEqual(error.severity, ErrorSeverity.ERROR)
        self.assertIsInstance(error.context, ErrorContext)
        self.assertIsNone(error.cause)

    def test_error_with_context(self) -> None:
        """Test creating an error with context information."""
        context = ErrorContext(
            component="test_component",
            operation="test_operation",
            details={"key": "value"},
        )
        error = BaseError(
            "Something went wrong",
            code="TEST_ERROR",
            category=ErrorCategory.RUNTIME,
            severity=ErrorSeverity.WARNING,
            context=context,
        )
        self.assertEqual(error.code, "TEST_ERROR")
        self.assertEqual(error.category, ErrorCategory.RUNTIME)
        self.assertEqual(error.severity, ErrorSeverity.WARNING)
        self.assertEqual(error.context.component, "test_component")
        self.assertEqual(error.context.operation, "test_operation")
        self.assertEqual(error.context.details, {"key": "value"})

    def test_validation_error(self) -> None:
        """Test creating a validation error."""
        error = ValidationError(
            "Invalid input",
            field="username",
            value="",
            details={"min_length": 3},
        )
        self.assertEqual(error.code, "VALIDATION_ERROR")
        self.assertEqual(error.category, ErrorCategory.VALIDATION)
        self.assertEqual(error.context.details["field"], "username")
        self.assertEqual(error.context.details["value"], "")
        self.assertEqual(error.context.details["min_length"], 3)

    def test_configuration_error(self) -> None:
        """Test creating a configuration error."""
        error = ConfigurationError(
            "Invalid configuration",
            config_key="api_key",
            details={"reason": "missing"},
        )
        self.assertEqual(error.code, "CONFIGURATION_ERROR")
        self.assertEqual(error.category, ErrorCategory.CONFIGURATION)
        self.assertEqual(error.context.details["config_key"], "api_key")
        self.assertEqual(error.context.details["reason"], "missing")

    def test_retryable_error(self) -> None:
        """Test creating a retryable error."""
        error = RetryableError(
            "Temporary failure",
            max_retries=5,
            retry_delay=2.0,
            details={"reason": "timeout"},
        )
        self.assertEqual(error.code, "RETRYABLE_ERROR")
        self.assertEqual(error.category, ErrorCategory.RUNTIME)
        self.assertEqual(error.severity, ErrorSeverity.WARNING)
        self.assertEqual(error.context.details["max_retries"], 5)
        self.assertEqual(error.context.details["retry_delay"], 2.0)
        self.assertEqual(error.context.details["reason"], "timeout")

    def test_integration_error(self) -> None:
        """Test creating an integration error."""
        error = IntegrationError(
            "Failed to connect to service",
            system="payment_gateway",
            details={"status_code": 500},
        )
        self.assertEqual(error.code, "INTEGRATION_ERROR")
        self.assertEqual(error.category, ErrorCategory.INTEGRATION)
        self.assertEqual(error.context.details["system"], "payment_gateway")
        self.assertEqual(error.context.details["status_code"], 500)


class TestErrorHandlingUtils(unittest.TestCase):
    """Test cases for error handling utilities."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.handler = logging.StreamHandler(sys.stderr)
        self.logger.addHandler(self.handler)
        self.handler.stream = MagicMock()

    def test_log_error(self) -> None:
        """Test logging an error with the log_error function."""
        # Create a string buffer to capture log output

        log_stream = StringIO()

        # Configure the logger to use our stream with a formatter that includes the message
        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
        handler.setFormatter(formatter)

        logger = logging.getLogger("test_logger")
        logger.setLevel(logging.ERROR)
        logger.handlers = [handler]

        # Log the error
        error = ValidationError("Invalid input", field="username")
        log_error(error, "Custom message", {"extra": "data"}, logger)

        # Get the log output
        log_output = log_stream.getvalue()

        # Check that the error was logged with the expected format
        self.assertIn(
            "ERROR:test_logger:Custom message: VALIDATION_ERROR: Invalid input",
            log_output,
        )

        # Check the error details
        self.assertEqual(error.context.details.get("field"), "username")

    @patch("logging.basicConfig")
    def test_setup_logging(self, mock_basic_config: MagicMock) -> None:
        """Test setting up logging configuration."""
        setup_logging(logging.DEBUG, "/tmp/test.log")
        mock_basic_config.assert_called_once()
        args, kwargs = mock_basic_config.call_args
        self.assertEqual(kwargs["level"], logging.DEBUG)
        self.assertEqual(len(kwargs["handlers"]), 2)  # stderr and file handler

    def test_handle_errors_context_manager(self) -> None:
        """Test the handle_errors context manager."""
        with self.assertLogs(__name__, level="ERROR") as cm:
            with self.assertRaises(ValueError):
                with handle_errors("test_component", "test_operation", logger=self.logger):
                    raise ValueError("Something went wrong")

        # Check that the error was logged
        self.assertIn("Error in test_component.test_operation", cm.output[0])
        self.assertIn("ValueError: Something went wrong", cm.output[0])

    def test_error_handler_decorator(self) -> None:
        """Test the error_handler decorator."""
        # Import the error_handler first to get a reference to the real function

        # Create a mock logger
        mock_logger = unittest.mock.Mock()

        # Replace the logger in the errors module with our mock
        with unittest.mock.patch("evoseal.core.errors.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger

            # Define the function inside the patch context
            @error_handler(ValueError, logger=mock_logger)
            def failing_function() -> None:
                raise ValueError("Test error")

            # Verify the error is raised
            with self.assertRaises(ValueError):
                failing_function()

            # Verify the error was logged
            mock_logger.log.assert_called_once()

            # Get the log level and message from the call
            log_level = mock_logger.log.call_args[0][0]
            log_message = mock_logger.log.call_args[0][1]

            self.assertEqual(log_level, logging.ERROR)
            self.assertIn(
                "Error in tests.unit.test_error_handling.failing_function: Test error",
                log_message,
            )

    def test_retry_on_error_decorator(self) -> None:
        """Test the retry_on_error decorator."""
        call_count = 0
        max_retries = 2  # Number of retry attempts

        # This function will fail on the first 3 calls (initial + max_retries)
        @retry_on_error(
            max_retries=max_retries,
            delay=0.1,
            backoff=1.0,
            exceptions=(ValueError,),
            logger=self.logger,
        )
        def flaky_function() -> int:
            nonlocal call_count
            call_count += 1
            # Always fail to test retry behavior
            raise ValueError("Temporary failure")

        # Reset call count before test
        call_count = 0

        # Test with logging - should raise after max_retries attempts
        with self.assertRaises(ValueError):
            with self.assertLogs(__name__, level="WARNING") as log_context:
                flaky_function()

        # The function should be called max_retries + 1 times (initial + max_retries)
        expected_calls = max_retries + 1
        self.assertEqual(
            call_count,
            expected_calls,
            f"Expected {expected_calls} calls (initial + {max_retries} retries), got {call_count}",
        )

        # Verify the number of retry logs (should equal max_retries)
        retry_logs = [msg for msg in log_context.output if "Retrying flaky_function" in msg]
        self.assertEqual(
            len(retry_logs),
            max_retries,
            f"Expected {max_retries} retry logs, got {len(retry_logs)}",
        )

        # Verify log messages contain correct attempt numbers and error message
        for i in range(max_retries):
            self.assertIn(
                f"({i+1}/{max_retries})",
                retry_logs[i],
                f"Retry log {i+1} missing attempt number",
            )
            self.assertIn(
                "Temporary failure",
                retry_logs[i],
                f"Retry log {i+1} missing error message",
            )

        # Verify the final error log is present
        error_logs = [msg for msg in log_context.output if "Max retries" in msg]
        self.assertEqual(len(error_logs), 1, f"Expected 1 error log, got {len(error_logs)}")
        self.assertIn(
            f"Max retries ({max_retries}) exceeded for flaky_function",
            error_logs[0],
            "Error log missing expected message",
        )

    def test_error_boundary_decorator(self) -> None:
        """Test the error_boundary decorator."""
        # Patch the logger in the errors module
        with unittest.mock.patch("evoseal.core.errors.logging") as mock_logging:
            # Create a mock logger
            mock_logger = unittest.mock.Mock()
            mock_logging.getLogger.return_value = mock_logger

            # Import the error_boundary after patching to ensure it uses our mock

            @error_boundary(default=0, exceptions=(ZeroDivisionError,))
            def divide(a: int, b: int) -> float:
                return a / b

            # Call the function that will trigger the error
            result = divide(10, 0)

            # Verify the default value is returned
            self.assertEqual(result, 0)

            # Verify the error was logged
            mock_logger.error.assert_called_once()
            error_message = mock_logger.error.call_args[0][0]
            self.assertIn("Error in divide: division by zero", error_message)

    def test_create_error_response(self) -> None:
        """Test creating an error response dictionary."""
        error = ValidationError(
            "Invalid input",
            field="email",
            details={"format": "must be a valid email"},
        )

        response = create_error_response(
            error,
            status_code=400,
            include_traceback=True,
        )

        error_data = response["error"]
        self.assertEqual(error_data["type"], "ValidationError")
        self.assertEqual(error_data["message"], "VALIDATION_ERROR: Invalid input")
        self.assertEqual(error_data["status"], 400)
        self.assertEqual(error_data["code"], "VALIDATION_ERROR")
        self.assertEqual(error_data["category"], "VALIDATION")
        self.assertEqual(error_data["severity"], "ERROR")
        self.assertEqual(error_data["context"]["details"]["field"], "email")
        self.assertIn("traceback", error_data)


if __name__ == "__main__":
    unittest.main()
