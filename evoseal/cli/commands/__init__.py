"""
Command modules for the EVOSEAL CLI.

This package contains all the command modules that implement the CLI functionality.
"""

from pathlib import Path
from typing import Any, Optional, TypeVar, Union

import typer

# Create a type variable for the command class
T = TypeVar("T", bound="EVOSEALCommand")


class EVOSEALCommand:
    """Base class for EVOSEAL CLI commands with common functionality."""

    def __init__(self, project_root: Optional[Union[Path, str]] = None, **kwargs: Any) -> None:
        """Initialize the command with an optional project root.

        Args:
            project_root: Path to the project root. If None, will be detected.
            **kwargs: Additional keyword arguments for subclasses.
        """
        self._project_root: Optional[Path] = None
        if project_root is not None:
            self._project_root = Path(project_root).resolve()

    @property
    def project_root(self) -> Path:
        """Get the project root directory.

        Returns:
            Path to the project root directory.

        Raises:
            FileNotFoundError: If project root cannot be found.
        """
        if self._project_root is None:
            self._project_root = self.get_project_root()
        return self._project_root

    @classmethod
    def get_project_root(cls, path: Optional[Path] = None) -> Path:
        """Find the project root directory.

        Args:
            path: Starting path to search from. Defaults to current directory.

        Returns:
            Path to the project root directory.

        Raises:
            FileNotFoundError: If project root cannot be found.
        """
        if path is None:
            path = Path.cwd()

        # Look for project root markers
        markers = ["pyproject.toml", ".git", "setup.py", ".evoseal"]

        current = Path(path).resolve()
        while True:
            if any((current / marker).exists() for marker in markers):
                return current

            parent = current.parent
            if parent == current:
                # Reached filesystem root
                raise FileNotFoundError(
                    "Could not find project root. Are you in the EVOSEAL project directory?\n"
                    "Try running 'evoseal init' to initialize a new project."
                )
            current = parent


# Import all command modules to register them with Typer
# This must be done after the base class is defined
from . import (  # noqa: E402
    config,
    dgm,
    export,
    init,
    openevolve,
    pipeline,
    seal,
    start,
    status,
    stop,
)

# List of all command modules for easy access
COMMAND_MODULES = [
    config,
    dgm,
    openevolve,
    export,
    init,
    pipeline,
    seal,
    start,
    status,
    stop,
]

# Make the app attribute available at the package level
app = typer.Typer(no_args_is_help=True)

# Add all commands to the app
for module in COMMAND_MODULES:
    if hasattr(module, "app") and module.app is not None:
        app.add_typer(module.app, name=module.app.info.name)
