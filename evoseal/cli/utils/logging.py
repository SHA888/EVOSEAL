"""
Logging utilities for EVOSEAL CLI.

This module provides enhanced logging functionality with rich formatting,
file output, and level-based filtering.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.logging import RichHandler


class EVOSEALLogger:
    """Enhanced logger for EVOSEAL with rich formatting and file output."""

    def __init__(
        self,
        name: str = "evoseal",
        level: str = "INFO",
        log_file: Optional[str] = None,
        console_output: bool = True,
        rich_formatting: bool = True,
    ):
        self.name = name
        self.level = level
        self.log_file = log_file
        self.console_output = console_output
        self.rich_formatting = rich_formatting

        self.logger = logging.getLogger(name)
        self.console = Console()

        self._setup_logger()

    def _setup_logger(self):
        """Setup the logger with handlers and formatters."""
        # Clear existing handlers
        self.logger.handlers.clear()

        # Set level
        log_level = getattr(logging, self.level.upper(), logging.INFO)
        self.logger.setLevel(log_level)

        # File handler
        if self.log_file:
            self._setup_file_handler()

        # Console handler
        if self.console_output:
            self._setup_console_handler()

    def _setup_file_handler(self):
        """Setup file handler for logging to file."""
        if not self.log_file:
            return

        # Ensure log directory exists
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(self.logger.level)

        # File formatter (detailed)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)

        self.logger.addHandler(file_handler)

    def _setup_console_handler(self):
        """Setup console handler for logging to terminal."""
        if self.rich_formatting:
            # Rich handler for beautiful console output
            console_handler = RichHandler(
                console=self.console, show_time=True, show_path=False, rich_tracebacks=True
            )
        else:
            # Standard console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = logging.Formatter('%(levelname)s - %(message)s')
            console_handler.setFormatter(console_formatter)

        console_handler.setLevel(self.logger.level)
        self.logger.addHandler(console_handler)

    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance."""
        return self.logger

    def set_level(self, level: str):
        """Change the logging level."""
        self.level = level
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.setLevel(log_level)

        # Update handler levels
        for handler in self.logger.handlers:
            handler.setLevel(log_level)

    def add_file_output(self, log_file: str):
        """Add file output to the logger."""
        self.log_file = log_file
        self._setup_file_handler()

    def remove_file_output(self):
        """Remove file output from the logger."""
        # Remove file handlers
        self.logger.handlers = [
            h for h in self.logger.handlers if not isinstance(h, logging.FileHandler)
        ]
        self.log_file = None

    def log_command_start(self, command: str, args: Dict[str, Any]):
        """Log the start of a command execution."""
        self.logger.info(f"Starting command: {command}")
        if args:
            self.logger.debug(f"Command arguments: {args}")

    def log_command_end(self, command: str, success: bool, duration: float):
        """Log the end of a command execution."""
        status = "completed" if success else "failed"
        self.logger.info(f"Command {command} {status} in {duration:.2f}s")

    def log_pipeline_stage(self, stage: str, iteration: int, status: str):
        """Log pipeline stage information."""
        self.logger.info(f"Pipeline iteration {iteration}: {stage} - {status}")

    def log_error_with_context(self, error: Exception, context: Dict[str, Any]):
        """Log an error with additional context."""
        self.logger.error(f"Error: {str(error)}")
        if context:
            self.logger.debug(f"Error context: {context}")
        self.logger.exception("Full traceback:")


# Global logger instance
_global_logger: Optional[EVOSEALLogger] = None


def get_logger(
    name: str = "evoseal",
    level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True,
    rich_formatting: bool = True,
) -> EVOSEALLogger:
    """Get or create a global logger instance."""
    global _global_logger

    if _global_logger is None:
        _global_logger = EVOSEALLogger(
            name=name,
            level=level,
            log_file=log_file,
            console_output=console_output,
            rich_formatting=rich_formatting,
        )

    return _global_logger


def setup_logging_from_config(config: Dict[str, Any]) -> EVOSEALLogger:
    """Setup logging from configuration dictionary."""
    logging_config = config.get("logging", {})

    return get_logger(
        level=logging_config.get("level", "INFO"),
        log_file=logging_config.get("file"),
        console_output=logging_config.get("console", True),
        rich_formatting=logging_config.get("rich", True),
    )


def log_command_execution(command_name: str):
    """Decorator to log command execution."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger()
            logger.log_command_start(command_name, kwargs)

            import time

            start_time = time.time()
            success = True

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                logger.log_error_with_context(e, {"command": command_name, "args": kwargs})
                raise
            finally:
                duration = time.time() - start_time
                logger.log_command_end(command_name, success, duration)

        return wrapper

    return decorator
