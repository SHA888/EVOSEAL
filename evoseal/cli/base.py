"""
Base command class for EVOSEAL CLI commands.
"""

import abc
import logging
import typing
from typing import Any, Callable, Optional, TypeVar, Union, cast

import typer
from click import Group as ClickGroup

# Type variable for the command function type
F = TypeVar("F", bound=Callable[..., Any])


class EVOSEALCommand(abc.ABC, typer.Typer):
    """Base class for all EVOSEAL CLI commands.

    This class provides common functionality and interface for all CLI commands.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the command with common settings."""
        super().__init__(*args, no_args_is_help=True, help=self.__doc__, **kwargs)

    @abc.abstractmethod
    def callback(
        self,
        *,
        cls: Union[type[ClickGroup], None] = None,
        invoke_without_command: bool = False,
        no_args_is_help: bool = True,
        subcommand_metavar: Union[str, None] = None,
        chain: bool = False,
        result_callback: Union[typing.Callable[..., typing.Any], None] = None,
        context_settings: Union[dict[typing.Any, typing.Any], None] = None,
        help: Union[str, None] = None,
        epilog: Union[str, None] = None,
        short_help: Union[str, None] = None,
        options_metavar: str = "[OPTIONS]",
        add_help_option: bool = True,
        hidden: bool = False,
        deprecated: bool = False,
        rich_help_panel: Union[str, None] = None,
    ) -> typing.Callable[[typing.Callable[..., typing.Any]], typing.Callable[..., typing.Any]]:
        """The main entry point for the command.

        This method is called when the command is executed. It should be implemented
        by subclasses to define the command's behavior.

        Args:
            cls: The TyperGroup class to use for command groups.
            invoke_without_command: Whether to invoke the command even if no subcommand is provided.
            no_args_is_help: Whether to show help if no arguments are provided.
            subcommand_metavar: The metavar to use for subcommands in help text.
            chain: Whether to chain multiple commands.
            result_callback: A callback to process the result of the command.
            context_settings: Additional context settings for the command.
            help: Help text for the command.
            epilog: Epilog text for the command help.
            short_help: Short help text for the command.
            options_metavar: The metavar to use for options in help text.
            add_help_option: Whether to add a help option to the command.
            hidden: Whether to hide the command from help.
            deprecated: Whether the command is deprecated.
            rich_help_panel: The panel to use for rich help formatting.

        Returns:
            A decorator that can be applied to command functions.
        """
        return cast(
            typing.Callable[[typing.Callable[..., typing.Any]], typing.Callable[..., typing.Any]],
            super().callback(
                cls=cls,
                invoke_without_command=invoke_without_command,
                no_args_is_help=no_args_is_help,
                subcommand_metavar=subcommand_metavar,
                chain=chain,
                result_callback=result_callback,
                context_settings=context_settings,
                help=help or self.__doc__,
                epilog=epilog,
                short_help=short_help,
                options_metavar=options_metavar,
                add_help_option=add_help_option,
                hidden=hidden,
                deprecated=deprecated,
                rich_help_panel=rich_help_panel,
            ),
        )
