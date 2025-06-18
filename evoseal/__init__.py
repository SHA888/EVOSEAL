"""
EVOSEAL - An advanced AI system integrating DGM, OpenEvolve, and SEAL.

This package provides a comprehensive framework for evolutionary AI development,
combining dynamic genetic modeling, evolutionary computation, and self-adapting
language models.
"""

from __future__ import annotations

import logging
from importlib.metadata import version as _get_version
from typing import Any, TypeVar, cast

import structlog
from structlog.contextvars import bind_contextvars
from structlog.processors import TimeStamper, format_exc_info
from structlog.stdlib import add_log_level, filter_by_level
from structlog.types import Processor, WrappedLogger

from .__version__ import __version__, __version_info__

# Type variables
T = TypeVar("T")

# Core components
__all__ = [
    "__version__",
    "__version_info__",
    "configure_logging",
    "dgm",
    "openevolve",
    "seal",
]


# Lazy imports
class _LazyModule:
    """Lazy module importer to avoid circular imports."""

    def __init__(self, module_name: str) -> None:
        """Initialize the lazy module.

        Args:
            module_name: The name of the module to import lazily
        """
        self._module_name = module_name
        self._module: Any | None = None

    def __getattr__(self, name: str) -> Any:
        """Get an attribute from the lazily imported module."""
        if self._module is None:
            if self._module_name == "dgm":
                from . import dgm as module
            elif self._module_name == "openevolve":
                from . import openevolve as module
            elif self._module_name == "seal":
                from . import seal as module
            else:
                raise ImportError(f"Unknown module: {self._module_name}")
            self._module = module
        return getattr(self._module, name)


# Initialize lazy modules
dgm = _LazyModule("dgm")
openevolve = _LazyModule("openevolve")
seal = _LazyModule("seal")


# Get version from package metadata if installed
try:
    __version__ = _get_version("evoseal")
except ImportError:
    # Package not installed, use version from __version__.py
    pass


def configure_logging(level: int = logging.INFO, **kwargs: Any) -> None:
    """Configure logging for the EVOSEAL package.

    This function sets up both standard logging and structlog with sensible defaults.
    It supports both JSON and pretty-printed console output.

    Args:
        level: Logging level (default: logging.INFO)
        **kwargs: Additional keyword arguments for structlog configuration:
            - pretty: If True, use console output instead of JSON
            - logger_factory: Custom logger factory
            - wrapper_class: Custom wrapper class
            - cache_logger_on_first_use: Cache logger on first use (default: True)
    """
    # Configure standard logging
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Configure structlog processors
    processors: list[Processor] = [
        filter_by_level,
        add_log_level,
        TimeStamper(fmt="iso"),
        format_exc_info,
    ]

    # Add console or JSON renderer based on pretty flag
    if kwargs.get("pretty", False):
        from structlog.dev import ConsoleRenderer

        processors.append(ConsoleRenderer())
    else:
        from structlog.processors import JSONRenderer

        processors.append(JSONRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=kwargs.get("logger_factory"),
        wrapper_class=kwargs.get("wrapper_class"),
        cache_logger_on_first_use=kwargs.get("cache_logger_on_first_use", True),
    )


# Initialize logging with default configuration when module is imported
configure_logging()

# Clean up namespace - only keep public API
__all__ = [
    "__version__",
    "__version_info__",
    "configure_logging",
    "dgm",
    "openevolve",
    "seal",
]
