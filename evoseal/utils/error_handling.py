"""Error handling utilities for the EVOSEAL project.

This module provides utilities for consistent error handling, including error reporting,
logging, and error recovery strategies.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import sys
import time
import traceback
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, TypeVar, cast

from evoseal.core.errors import (
    BaseError,
    ConfigurationError,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    IntegrationError,
    RetryableError,
    ValidationError,
)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)


def setup_logging(
    log_level: int = logging.INFO,
    log_file: str | None = None,
) -> None:
    """Configure the root logger with the specified settings.

    Args:
        log_level: Logging level (e.g., logging.INFO, logging.DEBUG).
        log_file: Optional path to a log file. If not provided, logs to stderr.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


def log_error(
    error: Exception,
    message: str = "An error occurred",
    extra: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Log an error with context.

    Args:
        error: The exception that was raised
        message: Custom message to include in the log
        extra: Additional context to include in the log
        logger: Logger instance to use. If not provided, uses the root logger.
    """
    if logger is None:
        logger = logging.getLogger()

    extra = extra or {}
    extra["error_type"] = error.__class__.__name__
    extra["error_message"] = str(error)

    # Include the error details in the message for better visibility
    full_message = f"{message}: {error}"
    logger.error(full_message, extra=extra, exc_info=error)
    if isinstance(error, BaseError):
        extra.update(
            {
                "error_code": error.code,
                "error_category": error.category.value,
                "error_severity": error.severity.value,
                "context": {
                    "component": error.context.component,
                    "operation": error.context.operation,
                    "details": error.context.details,
                },
            }
        )

    # Determine log level based on error type
    log_level = logging.ERROR
    if isinstance(error, BaseError):
        if error.severity == ErrorSeverity.DEBUG:
            log_level = logging.DEBUG
        elif error.severity == ErrorSeverity.INFO:
            log_level = logging.INFO
        elif error.severity == ErrorSeverity.WARNING:
            log_level = logging.WARNING
        elif error.severity == ErrorSeverity.CRITICAL:
            log_level = logging.CRITICAL

    # Log the error
    logger.log(
        log_level,
        message or str(error) or "An unknown error occurred",
        exc_info=True,
        extra={"error": extra},
    )


@contextmanager
def handle_errors(
    component: str | None = None,
    operation: str | None = None,
    reraise: bool = True,
    logger: logging.Logger | None = None,
) -> Generator[None, None, None]:
    """Context manager for handling errors with consistent logging.

    Args:
        component: Name of the component where the error occurred.
        operation: Name of the operation being performed.
        reraise: Whether to re-raise the exception after handling it.
        logger: Logger instance to use. If None, uses the module logger.

    Yields:
        None

    Raises:
        Exception: The original exception if reraise is True.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        yield
    except Exception as e:
        # Create error context
        context = ErrorContext(
            component=component,
            operation=operation,
        )

        # Log the error
        log_error(
            error=e,
            message=f"Error in {component or 'unknown'}.{operation or 'unknown'}",
            extra={"context": context.__dict__},
            logger=logger,
        )

        if reraise:
            raise


def error_handler(
    *error_types: type[BaseException],
    default_message: str = "An error occurred",
    log_level: int = logging.ERROR,
    reraise: bool = True,
    logger: logging.Logger | None = None,
) -> Callable[[F], F]:
    """Decorator to handle specific exceptions in a consistent way.

    Args:
        error_types: Exception types to catch. If not provided, catches all exceptions.
        default_message: Default message to use if the exception doesn't have one.
        log_level: Logging level to use when logging the error.
        reraise: Whether to re-raise the exception after handling it.
        logger: Logger instance to use. If None, uses the module logger.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Only handle the exception if it's one of the specified types
                # or if no specific types were provided
                if error_types and not isinstance(e, error_types):
                    raise

                # Get function signature for better error context
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                # Create context for the error
                context = {
                    "function": f"{func.__module__}.{func.__name__}",
                    "args": {k: str(v) for k, v in bound_args.arguments.items()},
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }

                # Log the error with context
                logger.log(
                    log_level,
                    f"Error in {func.__module__}.{func.__name__}: {str(e) or default_message}",
                    exc_info=sys.exc_info(),
                    extra=context,
                )

                if reraise:
                    raise

                # If we get here, return None as the default value
                return None

        return cast(F, wrapper)

    return decorator


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    logger: logging.Logger | None = None,
) -> Callable[[F], F]:
    """Retry a function when specified exceptions are raised.

    Args:
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries in seconds.
        backoff: Backoff multiplier (e.g., 2.0 means double the delay each retry).
        exceptions: Tuple of exceptions to catch and retry on.
        logger: Logger to use for logging retries. If None, uses module logger.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            mtries, mdelay = max_retries, delay

            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    mtries -= 1
                    if mtries == 0:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}",
                            exc_info=True,
                        )
                        raise

                    logger.warning(
                        f"Retrying {func.__name__} in {mdelay} seconds... "
                        f"({max_retries - mtries}/{max_retries}): {e}"
                    )
                    time.sleep(mdelay)
                    mdelay *= backoff

            return func(*args, **kwargs)  # This line should theoretically never be reached

        return cast(F, wrapper)

    return decorator


def error_boundary(
    default: Any = None,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    logger: logging.Logger | None = None,
) -> Callable[[F], F]:
    """Decorator to catch and log exceptions, returning a default value.

    Args:
        default: Default value to return if an exception is caught.
        exceptions: Tuple of exceptions to catch.
        logger: Logger to use for logging errors. If None, uses module logger.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                return default

        return cast(F, wrapper)

    return decorator


def create_error_response(
    error: Exception,
    status_code: int = 500,
    include_traceback: bool = False,
) -> dict[str, Any]:
    """Create a standardized error response dictionary.

    Args:
        error: The exception that occurred.
        status_code: HTTP status code to include in the response.
        include_traceback: Whether to include the full traceback in the response.

    Returns:
        A dictionary containing error details in a standardized format.
    """
    # Build the base response
    response = {
        "error": {
            "type": error.__class__.__name__,
            "message": str(error),
            "status": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceback": traceback.format_exc() if include_traceback else None,
        }
    }

    # Add BaseError specific fields if this is a BaseError
    if isinstance(error, BaseError):
        response["error"].update(
            {
                "code": error.code,
                "category": error.category.value,
                "severity": error.severity.value,
                "context": {
                    "component": error.context.component,
                    "operation": error.context.operation,
                    "details": error.context.details,
                },
            }
        )
    else:
        # For non-BaseError exceptions, include basic context
        response["error"].update(
            {
                "code": "UNKNOWN_ERROR",
                "category": ErrorCategory.UNKNOWN.value,
                "severity": ErrorSeverity.ERROR.value,
                "context": {
                    "component": None,
                    "operation": None,
                    "details": {},
                },
            }
        )

    return response
