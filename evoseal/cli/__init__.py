"""
EVOSEAL Command Line Interface

This module provides the main entry point for the EVOSEAL CLI
and common utilities for all CLI commands.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, Callable, TypeVar, Union

import typer
from typing_extensions import ParamSpec, TypeAlias

# Import the base command class for use in subcommands
from .base import EVOSEALCommand

# Type variables for generic type hints
P = ParamSpec("P")
T = TypeVar("T")

# Import the main CLI app
from .main import app, run  # noqa: E402

# Re-export the main CLI components
__all__ = [
    "app",
    "run",
    "EVOSEALCommand",
]

# Version of the EVOSEAL CLI
__version__ = "0.1.0"

# Type aliases
JSONType: TypeAlias = Union[dict[str, Any], list[Any], str, int, float, bool, None]
PathLike: TypeAlias = Union[str, Path]

# Global configuration paths
DEFAULT_CONFIG_DIR = Path(".evoseal")
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"


def get_version() -> str:
    """Get the current version of the EVOSEAL CLI.

    Returns:
        str: The current version string.
    """
    return __version__


def print_version() -> None:
    """Print the current version of the EVOSEAL CLI to stdout."""
    typer.echo(f"EVOSEAL CLI v{__version__}")


def ensure_config_dir() -> Path:
    """Ensure the EVOSEAL config directory exists.

    Returns:
        Path: Path to the config directory.
    """
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_CONFIG_DIR


def get_config_path() -> Path:
    """Get the path to the EVOSEAL config file.

    Returns:
        Path: Path to the config file.
    """
    return DEFAULT_CONFIG_FILE


def load_config(config_path: PathLike | None = None) -> dict[str, Any]:
    """Load the EVOSEAL configuration.

    Args:
        config_path: Path to the configuration file. If None, uses the default path.

    Returns:
        dict[str, Any]: The loaded configuration.
    """
    import yaml

    if config_path is None:
        config_path = get_config_path()
    else:
        config_path = Path(config_path) if not isinstance(config_path, Path) else config_path

    if not config_path.exists():
        return {}

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
        return config if isinstance(config, dict) else {}


def save_config(config: dict[str, Any], config_path: PathLike | None = None) -> None:
    """Save the EVOSEAL configuration.

    Args:
        config: The configuration to save.
        config_path: Optional path to the config file. If not provided, uses the default.
    """
    import yaml

    if config_path is None:
        config_path = get_config_path()
    else:
        config_path = Path(config_path)

    # Ensure the parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


# Import subcommands to register them
# These imports are at the bottom to avoid circular imports
from evoseal.cli.commands import (  # noqa: E402
    config,
    dgm,
    export,
    init,
    openevolve,
    seal,
    start,
    status,
    stop,
)

# Add subcommands to the main app
app.add_typer(init.app, name="init", help="Initialize a new EVOSEAL project")
app.add_typer(config.app, name="config", help="Manage configuration")
app.add_typer(seal.app, name="seal", help="SEAL (Self-Adapting Language Models) model operations")
app.add_typer(openevolve.app, name="openevolve", help="OpenEvolve processes")
app.add_typer(dgm.app, name="dgm", help="DGM code improvement workflows")
app.add_typer(start.app, name="start", help="Start background processes")
app.add_typer(stop.app, name="stop", help="Stop background processes")
app.add_typer(status.app, name="status", help="Show system status")
app.add_typer(export.app, name="export", help="Export results/variants")

# Version callback
version_callback = typer.Option(
    None,
    "--version",
    "-v",
    help="Show version and exit.",
    callback=lambda _: typer.echo("EVOSEAL CLI v0.1.0"),
    is_eager=True,
)

# Add version flag to the app
app.callback(invoke_without_command=True)(lambda version: None)
