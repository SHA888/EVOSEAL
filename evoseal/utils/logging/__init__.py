"""
Logging Utilities

This module provides enhanced logging with:
- JSON formatting for structured logging
- Context tracking for request/operation correlation
- Performance monitoring
- Error tracking and reporting
"""

from __future__ import annotations

import json
import logging
import logging.config
import logging.handlers
import os
import platform
import sys
import time
import traceback
import uuid
from collections.abc import Callable, Mapping, MutableMapping
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast, overload

import yaml

# Type variables for generic function wrapping
F = TypeVar("F", bound=Callable[..., Any])
LogRecordDict = MutableMapping[str, Any]  # Type for log record dictionary
ContextDict = dict[str, Any]  # Type for context dictionary


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    This formatter converts log records into JSON format for better machine
    readability and structured log processing.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log record
        """
        log_record: LogRecordDict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": record.process,
            "thread": record.thread,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "hostname": platform.node(),
        }

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Add any extra attributes
        extra = getattr(record, "extra", {})
        if isinstance(extra, Mapping):
            log_record.update(extra)
        elif extra is not None:
            log_record["extra"] = str(extra)

        try:
            return json.dumps(log_record, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            # Fallback to string representation if JSON serialization fails
            log_record["json_error"] = str(e)
            return json.dumps(
                {"error": "Failed to serialize log record", "message": str(record.msg)}
            )


class ContextFilter(logging.Filter):
    """Add contextual information to log records.

    This filter adds contextual information (like request ID, user ID, etc.)
    to all log records that pass through it.
    """

    def __init__(self, context: ContextDict | None = None) -> None:
        """Initialize the context filter.

        Args:
            context: Optional initial context dictionary
        """
        super().__init__()
        self._context: ContextDict = {}
        self._request_id: str | None = None
        if context:
            self.set_context(context)

    def set_context(self, context: ContextDict) -> None:
        """Set the context for this filter.

        Args:
            context: Dictionary of context values to add to log records
        """
        self._context = context.copy()
        # Update request_id if it's in the context
        if "request_id" in context:
            self._request_id = context["request_id"]

    def set_request_id(self, request_id: str) -> None:
        """Set the request ID for correlation.

        Args:
            request_id: The request ID to use for correlation
        """
        self._request_id = request_id
        self._context["request_id"] = request_id

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record.

        Args:
            record: The log record to add context to

        Returns:
            bool: Always returns True to indicate the record should be processed
        """
        # Add request ID and hostname to the record using direct attribute access
        if not hasattr(record, "request_id") or record.request_id is None:
            record.request_id = self._request_id if self._request_id is not None else "global"

        if not hasattr(record, "hostname") or record.hostname is None:
            record.hostname = platform.node()

        # For dynamic context keys, still use getattr/setattr
        for key, value in self._context.items():
            if not hasattr(record, key) or getattr(record, key) is None:
                setattr(record, key, value)

        return True


class PerformanceFilter(logging.Filter):
    """Filter for performance-related log records.

    This filter only allows log records that have a 'performance_metric' attribute,
    which is typically added by the log_performance method.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Determine if the record is a performance metric.

        Args:
            record: The log record to check

        Returns:
            bool: True if the record is a performance metric, False otherwise
        """
        return hasattr(record, "performance_metric")


def setup_logging(
    config_path: str | Path | None = None,
    default_level: int = logging.INFO,
    env_key: str = "LOG_CFG",
    context: ContextDict | None = None,
) -> logging.Logger:
    """Set up logging configuration from YAML file.

    This function configures the Python logging system using a YAML configuration
    file. It supports both file-based and environment-variable-based configuration
    paths, with sensible defaults.

    Args:
        config_path: Path to the logging configuration YAML file. If None,
                   will check the environment variable specified by env_key.
        default_level: Default logging level to use if config loading fails.
        env_key: Name of the environment variable that may contain the path to
               the logging configuration file.
        context: Optional context dictionary to add to all log records.

    Returns:
        The configured root logger instance.

    Example:
        >>> logger = setup_logging("config/logging.yaml")
        >>> logger.info("Logging configured successfully")
    """
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True, parents=True)

    # Resolve config path
    if config_path is None:
        config_path = os.getenv(env_key)

    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "logging.yaml"
    else:
        config_path = Path(config_path)

    # Configure logging
    try:
        with open(config_path, encoding="utf-8") as f:
            try:
                config = yaml.safe_load(f)
                if not isinstance(config, dict):
                    raise ValueError("Logging config must be a dictionary")

                # Apply the configuration
                logging.config.dictConfig(config)

                # Set up context filter if context is provided
                if context:
                    logger = logging.getLogger("evoseal")
                    for filter_ in logger.filters:
                        if isinstance(filter_, ContextFilter):
                            filter_.set_context(context)
                            break

            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in logging config: {e}") from e

    except FileNotFoundError:
        logging.basicConfig(level=default_level)
        logging.warning(
            f"Logging config file not found at {config_path}. "
            f"Using basic config with level {logging.getLevelName(default_level)}"
        )
    except Exception as e:
        logging.basicConfig(level=default_level)
        logging.error(f"Error setting up logging: {e}. Using basic config.")

    return logging.getLogger("evoseal")


class LoggingMixin:
    """Mixin class that adds enhanced logging functionality to other classes.

    This mixin provides a logger property that creates a logger with the same name
    as the class it's mixed into, along with convenience methods for common logging
    operations like performance metrics.
    """

    # Class variable to store logger instances
    _logger: logging.Logger | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the logging mixin.

        Args:
            *args: Positional arguments passed to the parent class
            **kwargs: Keyword arguments passed to the parent class
        """
        super().__init__(*args, **kwargs)

    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance for this class.

        The logger is created on first access with a name based on the class's
        module and name. This ensures consistent logging across instances.

        Returns:
            A configured logger instance
        """
        # Use class logger if it exists
        if self._logger is not None:
            return self._logger

        # Otherwise create a new one
        logger_name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        self._logger = logging.getLogger(logger_name)
        return self._logger

    def log_performance(self, metric_name: str, value: float, **extra: Any) -> None:
        """Log a performance metric with additional context.

        This is a convenience method for logging performance metrics with a
        consistent format. The metric is logged at INFO level with additional
        context in the 'extra' dictionary.

        Args:
            metric_name: Name of the performance metric (e.g., 'request_latency_ms')
            value: Numeric value of the metric
            **extra: Additional metadata to include with the log record
        """
        if not hasattr(self, "_logger") or self._logger is None:
            # Ensure logger is initialized
            _ = self.logger

        extra_metrics = {
            "performance_metric": metric_name,
            "metric_value": value,
            **extra,
        }

        self.logger.info(f"Performance metric: {metric_name} = {value}", extra=extra_metrics)


@overload
def log_execution_time(logger: logging.Logger) -> Callable[[F], F]: ...


@overload
def log_execution_time(logger: None = ...) -> Callable[[F], F]: ...


def log_execution_time(
    logger: logging.Logger | None = None,
) -> Callable[[F], F]:
    """Decorator to log the execution time of a function.

    This decorator measures the time taken to execute the decorated function
    and logs it at the DEBUG level. If an exception occurs, it's logged at the
    ERROR level with a traceback.

    Args:
        logger: Logger instance to use for logging. If None, a logger will be
               created based on the decorated function's module.

    Returns:
        A decorator that can be applied to functions to log their execution time.

    Example:
        ```python
        @log_execution_time()
        def slow_function():
            time.sleep(1)

        # With a specific logger
        logger = logging.getLogger(__name__)

        @log_execution_time(logger)
        def another_function():
            time.sleep(2)
        ```
    """

    def decorator(func: F) -> F:
        nonlocal logger

        if logger is None:
            # Create a logger based on the function's module
            logger_ = logging.getLogger(func.__module__)
        else:
            logger_ = logger

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.monotonic()
            try:
                result = func(*args, **kwargs)
                duration = time.monotonic() - start_time
                logger_.debug(
                    "Function %s executed in %.4f seconds",
                    func.__name__,
                    duration,
                    extra={
                        "function": func.__name__,
                        "duration_seconds": duration,
                        "execution_time": duration,  # For backward compatibility with tests
                    },
                )
                return result
            except Exception as e:
                duration = time.monotonic() - start_time
                logger_.error(
                    "Error in %s after %.4f seconds: %s",
                    func.__name__,
                    duration,
                    str(e),
                    exc_info=True,
                    extra={
                        "function": func.__name__,
                        "duration_seconds": duration,
                        "error": str(e),
                    },
                )
                raise

        return cast(F, wrapper)

    return decorator


@overload
def with_request_id(logger: logging.Logger) -> Callable[[F], F]: ...


@overload
def with_request_id(logger: None = ...) -> Callable[[F], F]: ...


def with_request_id(logger: logging.Logger | None = None) -> Callable[[F], F]:
    """Decorator to add request ID to log context.

    This decorator generates a unique request ID for each function call and adds
    it to the log context. If the function returns a dictionary, the request ID
    is also added to the return value.

    Args:
        logger: Logger instance to use for logging. If None, a logger will be
               created based on the decorated function's module.

    Returns:
        A decorator that adds request ID to the log context.

    Example:
        ```python
        @with_request_id()
        def process_request(data):
            logger.info("Processing request")
            return {"status": "success"}

        # With a specific logger
        logger = logging.getLogger(__name__)

        @with_request_id(logger)
        def another_function():
            logger.info("Processing with custom logger")
        ```
    """

    def decorator(func: F) -> F:
        nonlocal logger

        if logger is None:
            # Create a logger based on the function's module
            logger_ = logging.getLogger(func.__module__)
        else:
            logger_ = logger

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate a new request ID if one doesn't exist
            request_id = str(uuid.uuid4())

            # Set up context for this request
            context = {"request_id": request_id}

            # Add context to all loggers
            for handler in logging.root.handlers:
                for filter_ in handler.filters:
                    if isinstance(filter_, ContextFilter):
                        filter_.set_request_id(request_id)
                        filter_.set_context(context)
                        break

            try:
                # Match the exact message format expected by the test
                logger_.info(
                    f"Starting request {request_id}",
                    extra={"request_id": request_id},
                )

                # Call the original function
                result = func(*args, **kwargs)
                # Add request ID to the result if it's a dictionary
                if isinstance(result, dict):
                    result["request_id"] = request_id

                # Match the exact message format expected by the test
                logger_.info(
                    f"Completed request {request_id}",
                    extra={"request_id": request_id},
                )

                return result

            except Exception as e:
                logger_.error(
                    "Request failed: %s",
                    str(e),
                    exc_info=True,
                    extra={"request_id": request_id, "error": str(e)},
                )
                raise
            finally:
                # Clean up the context
                for handler in logging.root.handlers:
                    for filter_ in handler.filters:
                        if isinstance(filter_, ContextFilter):
                            filter_.set_request_id("")
                            filter_.set_context({})

        return cast(F, wrapper)

    return decorator


def _setup_default_logging() -> None:
    """Set up default logging configuration if not already configured.

    This function is called when the module is imported to ensure that
    logging is properly configured with a default configuration if no
    other configuration has been applied.
    """
    # Only proceed if logging hasn't been configured yet
    if not logging.root.handlers:
        setup_logging()


# Initialize a default context filter
context_filter = ContextFilter()

# Add context filter to root logger
root_logger = logging.getLogger()
for handler in root_logger.handlers:
    if not any(isinstance(f, ContextFilter) for f in handler.filters):
        handler.addFilter(context_filter)

# Add context filter to evoseal logger
evoseal_logger = logging.getLogger("evoseal")
for handler in evoseal_logger.handlers:
    if not any(isinstance(f, ContextFilter) for f in handler.filters):
        handler.addFilter(context_filter)

# Set up default logging if not configured
_setup_default_logging()

# Re-export common logging functions for convenience
get_logger = logging.getLogger
basic_config = logging.basicConfig
capture_warnings = logging.captureWarnings

# Add type hints for better IDE support
if hasattr(logging, "getLoggerClass"):

    class Logger(logging.getLoggerClass()):  # type: ignore
        """Extended logger class with additional methods for type checking."""

        def __init__(self, name: str, level: int = logging.NOTSET) -> None:
            super().__init__(name, level)

        def performance(self, metric_name: str, value: float, **kwargs: Any) -> None:
            """Log a performance metric.

            Args:
                metric_name: Name of the performance metric
                value: Numeric value of the metric
                **kwargs: Additional context for the log record
            """
            self.info(
                f"Performance metric: {metric_name} = {value}",
                extra={
                    "performance_metric": metric_name,
                    "metric_value": value,
                    **kwargs,
                },
            )

    # Set the custom logger class
    logging.setLoggerClass(Logger)
