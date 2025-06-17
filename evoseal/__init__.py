"""
EVOSEAL - An advanced AI system integrating DGM, OpenEvolve, and SEAL.

This package provides a comprehensive framework for evolutionary AI development,
combining dynamic genetic modeling, evolutionary computation, and self-adapting
language models.
"""

from importlib.metadata import version as _get_version

from .__version__ import __version__, __version_info__

# Core components
__all__ = [
    # Core functionality
    "__version__",
    "__version_info__",
    
    # Submodules
    "dgm",
    "openevolve",
    "seal",
]

try:
    __version__ = _get_version("evoseal")
except ImportError:
    # Package not installed, use version from __version__.py
    pass

# Initialize logging configuration
import logging
from structlog import configure as structlog_configure
from structlog.stdlib import add_log_level, filter_by_level
from structlog.processors import TimeStamper, format_exc_info
from structlog.threadlocal import wrap_dict

# Configure structlog
def configure_logging(level=logging.INFO, **kwargs):
    """Configure logging for the EVOSEAL package.
    
    Args:
        level: Logging level (default: logging.INFO)
        **kwargs: Additional keyword arguments for structlog configuration
    """
    processors = [
        filter_by_level,
        add_log_level,
        TimeStamper(fmt="iso"),
        format_exc_info,
    ]
    
    if kwargs.get("pretty", False):
        from structlog.dev import ConsoleRenderer
        processors.append(ConsoleRenderer())
    else:
        from structlog.processors import JSONRenderer
        processors.append(JSONRenderer())
    
    structlog_configure(
        processors=processors,
        context_class=wrap_dict(dict),
        logger_factory=kwargs.get("logger_factory"),
        wrapper_class=kwargs.get("wrapper_class"),
        cache_logger_on_first_use=kwargs.get("cache_logger_on_first_use", True),
    )
    
    # Set the root logger level
    logging.basicConfig(level=level)

# Initialize logging with default configuration
configure_logging()

# Import core functionality after logging is configured
from . import dgm, openevolve, seal  # noqa: E402

# Clean up namespace
del logging, structlog_configure, add_log_level, filter_by_level, TimeStamper, format_exc_info, wrap_dict