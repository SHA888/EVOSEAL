"""
Base command class for EVOSEAL CLI commands.
"""

import abc
from typing import Any, Optional

import typer


class EVOSEALCommand(abc.ABC, typer.Typer):
    """Base class for all EVOSEAL CLI commands.

    This class provides common functionality and interface for all CLI commands.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the command with common settings."""
        super().__init__(*args, no_args_is_help=True, help=self.__doc__, **kwargs)

    @abc.abstractmethod
    def callback(self) -> None:
        """The main entry point for the command."""
        ...
