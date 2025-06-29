"""Error handling framework for the EVOSEAL project.

This module defines a comprehensive error handling system with custom exceptions,
error classification, and utilities for consistent error handling across the application.
"""

from __future__ import annotations

import enum
import functools
import inspect
import logging
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar, cast, overload

T = TypeVar("T", bound="BaseError")
F = TypeVar("F", bound=Callable[..., Any])


class ErrorSeverity(enum.Enum):
    """Defines the severity levels for errors."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(enum.Enum):
    """Categories for different types of errors."""

    VALIDATION = "VALIDATION"
    CONFIGURATION = "CONFIGURATION"
    RUNTIME = "RUNTIME"
    INTEGRATION = "INTEGRATION"
    NETWORK = "NETWORK"
    PERMISSION = "PERMISSION"
    RESOURCE = "RESOURCE"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


@dataclass
class ErrorConfig:
    """Configuration for error creation."""

    code: str = "UNKNOWN_ERROR"
    category: ErrorCategory = ErrorCategory.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.ERROR
    context: ErrorContext | None = None
    cause: BaseException | None = None


@dataclass
class ErrorContext:
    """Contextual information about where and why an error occurred."""

    component: str | None = None
    operation: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class BaseError(Exception):
    """Base class for all custom exceptions in the application.

    Attributes:
        message: Human-readable error message.
        code: Application-specific error code.
        category: Category of the error.
        severity: Severity level of the error.
        context: Additional context about the error.
        cause: The original exception that caused this error, if any.
    """

    def __init__(
        self,
        message: str,
        config: ErrorConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error message.
            config: Optional error configuration. If not provided, a default one will be created.
            **kwargs: Additional configuration overrides.
        """
        self.message = message

        # Create or update config
        if config is None:
            config = ErrorConfig()

        # Apply any overrides from kwargs
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        self.code = config.code
        self.category = config.category
        self.severity = config.severity
        self.context = config.context or ErrorContext()
        self.cause = config.cause
        self.timestamp = datetime.now()

        # Format the error message with code and category
        full_message = f"{self.code}: {self.message}"
        if self.category != ErrorCategory.UNKNOWN:
            full_message = f"[{self.category.value}] {full_message}"

        super().__init__(full_message)

    def __str__(self) -> str:
        """Return a string representation of the error."""
        return f"{self.code}: {self.message}"

    def with_context(self: T, **kwargs: Any) -> T:
        """Add context to the error and return self for chaining."""
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)
            else:
                self.context.details[key] = value
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert the error to a dictionary for serialization."""
        return {
            "message": self.message,
            "code": self.code,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": {
                "component": self.context.component,
                "operation": self.context.operation,
                "details": self.context.details,
            },
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None,
        }

    @classmethod
    def from_exception(cls: type[T], exc: BaseException, **kwargs: Any) -> T:
        """Create an error instance from an existing exception."""
        if isinstance(exc, cls):
            return exc

        return cls(message=str(exc) or "An unknown error occurred", cause=exc, **kwargs)


# Specific error types
class ValidationError(BaseError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        **kwargs: Any,
    ) -> None:
        # Create context with validation details
        details = {"field": field, "value": value, **(kwargs.pop("details", {}) or {})}
        context = ErrorContext(
            component=kwargs.pop("component", None),
            operation=kwargs.pop("operation", None),
            details=details,
        )

        # Create config with validation-specific defaults
        config = ErrorConfig(
            code=kwargs.pop("code", "VALIDATION_ERROR"),
            category=ErrorCategory.VALIDATION,
            severity=kwargs.pop("severity", ErrorSeverity.ERROR),
            context=context,
        )

        super().__init__(message=message, config=config, **kwargs)


class ConfigurationError(BaseError):
    """Raised when there is a configuration issue."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        # Create context with configuration details
        details = {"config_key": config_key, **(kwargs.pop("details", {}) or {})}
        context = ErrorContext(
            component=kwargs.pop("component", None),
            operation=kwargs.pop("operation", None),
            details=details,
        )

        # Create config with configuration-specific defaults
        config = ErrorConfig(
            code=kwargs.pop("code", "CONFIGURATION_ERROR"),
            category=ErrorCategory.CONFIGURATION,
            severity=kwargs.pop("severity", ErrorSeverity.ERROR),
            context=context,
        )

        super().__init__(message=message, config=config, **kwargs)


class IntegrationError(BaseError):
    """Raised when there is an error integrating with an external system."""

    def __init__(
        self,
        message: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> None:
        # Create context with integration details
        details = {"system": system, **(kwargs.pop("details", {}) or {})}
        context = ErrorContext(
            component=kwargs.pop("component", None),
            operation=kwargs.pop("operation", None),
            details=details,
        )

        # Create config with integration-specific defaults
        config = ErrorConfig(
            code=kwargs.pop("code", "INTEGRATION_ERROR"),
            category=ErrorCategory.INTEGRATION,
            severity=kwargs.pop("severity", ErrorSeverity.ERROR),
            context=context,
        )

        super().__init__(message=message, config=config, **kwargs)


class RetryableError(BaseError):
    """Raised when an operation fails but can be retried."""

    def __init__(
        self,
        message: str,
        retry_delay: int | float | None = None,
        max_retries: int | None = None,
        **kwargs: Any,
    ) -> None:
        # Create context with retry details
        details = {
            "retry_delay": retry_delay,
            "max_retries": max_retries,
            **(kwargs.pop("details", {}) or {}),
        }
        context = ErrorContext(
            component=kwargs.pop("component", None),
            operation=kwargs.pop("operation", None),
            details=details,
        )

        # Create config with retry-specific defaults
        config = ErrorConfig(
            code=kwargs.pop("code", "RETRYABLE_ERROR"),
            category=ErrorCategory.RUNTIME,
            severity=kwargs.pop("severity", ErrorSeverity.WARNING),
            context=context,
        )

        super().__init__(message=message, config=config, **kwargs)


# Error handling utilities
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
        logger: Logger instance to use. If None, creates a new logger.
    """
    if not logger:
        logger = logging.getLogger(__name__)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:  # Catch all exceptions first
                # Check if we should handle this exception type
                if error_types and not isinstance(e, error_types):
                    raise

                # Handle the exception
                # Get function signature for better error context
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                # Log the error with context
                log_extra = {
                    "func_module": func.__module__,
                    "func_name": func.__name__,
                    "func_args": {k: str(v) for k, v in bound_args.arguments.items()},
                    "error_type": e.__class__.__name__,
                    "error_msg": str(e),
                }
                logger.log(
                    log_level,
                    f"Error in {func.__module__}.{func.__name__}: {str(e) or default_message}",
                    exc_info=sys.exc_info(),
                    extra=log_extra,
                )

                if reraise:
                    raise

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
            attempts = 0
            mdelay = delay

            while attempts <= max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts > max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}",
                            exc_info=True,
                        )
                        raise

                    logger.warning(
                        f"Retrying {func.__name__} in {mdelay} seconds... "
                        f"({attempts}/{max_retries}): {e}"
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
