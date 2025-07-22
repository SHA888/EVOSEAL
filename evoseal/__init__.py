"""
EVOSEAL - An advanced AI system integrating DGM, OpenEvolve, and SEAL (Self-Adapting Language Models).

This package provides a comprehensive framework for evolutionary AI development,
combining Darwin Godel Machine, OpenEvolve, and SEAL (Self-Adapting Language Models).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import structlog
from structlog.contextvars import bind_contextvars
from structlog.processors import TimeStamper, format_exc_info
from structlog.stdlib import add_log_level, filter_by_level

# Import version information early to avoid circular imports
from evoseal.__version__ import __version__, __version_info__

# Re-export core functionality
from evoseal.core import Controller, Evaluator, SelectionStrategy, VersionDatabase

# Core type stubs for type checking
if TYPE_CHECKING:
    from structlog.types import Processor, WrappedLogger

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias  # type: ignore[import-untyped,unused-ignore]

"""EVOSEAL: Evolutionary Self-Improving AI Agent Framework.

EVOSEAL is an advanced AI agent designed to solve complex tasks through code evolution
while continuously improving its own architecture.
"""

__all__ = [
    "Controller",
    "Evaluator",
    "SelectionStrategy",
    "VersionDatabase",
    "__version__",
    "__version_info__",
]

# Type variable for generic types
T_contra = TypeVar("T_contra", contravariant=True)  # For contravariant types

# Configuration dictionary to store settings
_config: dict[str, Any] = {}

# Type stubs for core components
CodeVariant: TypeAlias = Any
EvolutionConfig: TypeAlias = Any
EvolutionResult: TypeAlias = Any
FitnessFunction: TypeAlias = Any
MutationStrategy: TypeAlias = Any
# SelectionStrategy is imported from evoseal.core

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)

# Configure structlog for structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

# Create logger
logger = structlog.get_logger("evoseal")

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
    from importlib.metadata import version

    __version__ = version("evoseal")
    __version_info__ = tuple(int(i) for i in __version__.split(".") if i.isdigit())
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

# Version information for EVOSEAL
# Minimum Python version: 3.9
# This version should be kept in sync with pyproject.toml and setup.cfg
__version__ = "0.2.0"

# CLI functionality
if sys.version_info >= (3, 8):
    from importlib import metadata

    try:
        __version__ = metadata.version("evoseal")
    except metadata.PackageNotFoundError:
        pass  # Use the default version defined above
else:
    import importlib_metadata as metadata  # type: ignore[import-not-found]

    try:
        __version__ = metadata.version("evoseal")
    except metadata.PackageNotFoundError:
        pass  # Use the default version defined above

# Import the CLI app
from evoseal.cli import app, run  # noqa: E402

# Re-export the CLI app
__all__ = ["app", "run"]


def get_version() -> str:
    """Get the current version of EVOSEAL.

    Returns:
        str: The current version string.
    """
    return __version__


def print_version() -> None:
    """Print the current version of EVOSEAL to stdout."""
    print(f"EVOSEAL v{__version__}")


# Add a console script entry point for the CLI
def main() -> None:
    """Entry point for the EVOSEAL CLI."""
    run()


# This allows running the package with python -m evoseal
if __name__ == "__main__":
    main()

# Clean up namespace - only keep public API
__all__ = [
    "__version__",
    "__version_info__",
    "configure_logging",
    "dgm",
    "openevolve",
    "seal",
]
