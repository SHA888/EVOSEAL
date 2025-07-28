"""
EVOSEAL Command Line Interface

This module provides the main entry point for the EVOSEAL CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

# Import commands first to avoid circular imports
from evoseal.cli.commands import (
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

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def get_version() -> str:
    from evoseal import __version__

    return f"EVOSEAL v{__version__}"


# Create the main app with version flag support
app = typer.Typer(
    name="evoseal",
    help="EVOSEAL: Evolutionary Self-Improving AI Agent",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
)

# Add subcommands
app.add_typer(init.app, name="init", help="Initialize a new EVOSEAL project")
app.add_typer(config.app, name="config", help="Manage configuration")
app.add_typer(pipeline.app, name="pipeline", help="Pipeline control and monitoring")
app.add_typer(seal.app, name="seal", help="SEAL (Self-Adapting Language Models) model operations")
app.add_typer(openevolve.app, name="openevolve", help="OpenEvolve processes")
app.add_typer(dgm.app, name="dgm", help="DGM code improvement workflows")
app.add_typer(start.app, name="start", help="Start background processes")
app.add_typer(stop.app, name="stop", help="Stop background processes")
app.add_typer(status.app, name="status", help="Show system status")
app.add_typer(export.app, name="export", help="Export results/variants")


# Main callback with version flag support
def version_callback(value: bool) -> None:
    """Handle the --version flag."""
    if value:
        typer.echo(get_version())
        raise typer.Exit()


@app.callback(
    invoke_without_command=True,
    no_args_is_help=True,
    help="EVOSEAL: Evolutionary Self-Improving AI Agent",
)
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    )
) -> None:
    """EVOSEAL: Evolutionary Self-Improving AI Agent

    A unified command-line interface for the EVOSEAL system.
    """
    # This will only be reached if no subcommand is provided and --version is not used
    if len(sys.argv) == 1:
        # Use the context to show help
        ctx = typer.Context(typer.main.get_command(app))
        typer.echo(ctx.get_help())
        raise typer.Exit()


def run() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    run()
