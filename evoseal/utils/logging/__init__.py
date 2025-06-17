"""
Logging Utilities

This module provides enhanced logging with:
- JSON formatting for structured logging
- Context tracking for request/operation correlation
- Performance monitoring
- Error tracking and reporting
"""
import os
import sys
import json
import time
import uuid
import logging
import logging.config
import logging.handlers
import platform
import traceback
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Union, List, Callable, TypeVar, cast
from functools import wraps

# Type variable for generic function wrapping
F = TypeVar('F', bound=Callable[..., Any])

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format the log record as JSON."""
        log_record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'process': record.process,
            'thread': record.thread,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'hostname': platform.node(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        
        # Add any extra attributes
        if hasattr(record, 'extra') and isinstance(record.extra, dict):
            log_record.update(record.extra)
            
        return json.dumps(log_record, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """Add contextual information to log records."""
    
    def __init__(self, context: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.context = context or {}
        self.request_id = None
    
    def set_context(self, context: Dict[str, Any]) -> None:
        """Set the context for this filter."""
        self.context = context
        
    def set_request_id(self, request_id: str) -> None:
        """Set the request ID for correlation."""
        self.request_id = request_id
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record."""
        record.request_id = self.request_id or 'global'
        record.hostname = platform.node()
        
        # Add context as extra fields
        for key, value in self.context.items():
            setattr(record, key, value)
            
        return True


class PerformanceFilter(logging.Filter):
    """Filter for performance-related log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow performance-related records."""
        return hasattr(record, 'performance_metric')


def setup_logging(
    config_path: Optional[Union[str, Path]] = None,
    default_level: int = logging.INFO,
    env_key: str = 'LOG_CFG',
    context: Optional[Dict[str, Any]] = None
) -> logging.Logger:
    """
    Setup logging configuration from YAML file.
    
    Args:
        config_path: Path to the logging configuration file
        default_level: Default logging level
        env_key: Environment variable that can specify the path to the config file
        context: Optional context dictionary to add to all log records
        
    Returns:
        Root logger instance
    """
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    if config_path is None:
        # Try to get config path from environment variable
        config_path = os.getenv(env_key, None)
        
    if config_path is None:
        # Use default config path
        config_path = Path(__file__).parent.parent.parent / "config" / "logging.yaml"
    
    config_path = Path(config_path)
    
    try:
        with open(config_path, 'rt') as f:
            config = yaml.safe_load(f)
            
            # Apply config
            logging.config.dictConfig(config)
            
            # Set up context filter
            context_filter = logging.getLogger('evoseal').filters[0] if logging.getLogger('evoseal').filters else None
            if context_filter and isinstance(context_filter, ContextFilter) and context:
                context_filter.set_context(context)
                
    except Exception as e:
        print(f'Error loading logging config: {e}. Using basic config')
        logging.basicConfig(level=default_level)
    
    return logging.getLogger('evoseal')

class LoggingMixin:
    """Mixin class that adds enhanced logging functionality to other classes."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the logger for the class."""
        self._logger = None
        super().__init__(*args, **kwargs)
    
    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance.
        
        The logger is created on first access to ensure it's properly initialized.
        """
        if self._logger is None:
            self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        return self._logger
        
    def log_performance(self, metric_name: str, value: float, **extra: Any) -> None:
        """Log a performance metric.
        
        Args:
            metric_name: Name of the performance metric
            value: Numeric value of the metric
            **extra: Additional metadata for the metric
        """
        extra['performance_metric'] = metric_name
        extra['metric_value'] = value
        self._logger.info(f"Performance metric: {metric_name} = {value}", extra=extra)


def log_execution_time(logger: logging.Logger) -> Callable[[F], F]:
    """Decorator to log the execution time of a function.
    
    Args:
        logger: Logger instance to use for logging
        
    Returns:
        Decorated function that logs execution time
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.monotonic()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.monotonic() - start_time
                logger.debug(
                    f"Function {func.__qualname__} executed in {duration:.4f} seconds",
                    extra={
                        'function': func.__qualname__,
                        'execution_time': duration,
                        'module': func.__module__
                    }
                )
        return cast(F, wrapper)
    return decorator


def with_request_id(logger: logging.Logger) -> Callable[[F], F]:
    """Decorator to add request ID to log context.
    
    Args:
        logger: Logger instance to use for logging
        
    Returns:
        Decorated function that adds request ID to log context
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            request_id = str(uuid.uuid4())
            
            # Set request ID in context filters
            for handler in logger.handlers:
                for filter_ in handler.filters:
                    if isinstance(filter_, ContextFilter):
                        filter_.set_request_id(request_id)
            
            # Add request ID to log records
            extra = {'request_id': request_id}
            logger.info(f"Starting request {request_id}", extra=extra)
            
            try:
                result = func(*args, **kwargs)
                logger.info(f"Completed request {request_id}", extra=extra)
                return result
            except Exception as e:
                logger.error(
                    f"Request {request_id} failed: {str(e)}",
                    exc_info=True,
                    extra=extra
                )
                raise
        return cast(F, wrapper)
    return decorator


# Initialize a default context filter
context_filter = ContextFilter()

# Add context filter to root logger
root_logger = logging.getLogger()
for handler in root_logger.handlers:
    handler.addFilter(context_filter)

# Add context filter to evoseal logger
evoseal_logger = logging.getLogger('evoseal')
for handler in evoseal_logger.handlers:
    handler.addFilter(context_filter)

# Set up default logging if not configured
if not logging.root.handlers:
    setup_logging()
