"""
Stop background processes for the EVOSEAL CLI.
"""

from __future__ import annotations

import signal
import sys
from typing import Annotated

import typer

from ..base import EVOSEALCommand

app = typer.Typer(name="stop", help="Stop background processes")


@app.callback()
def main() -> None:
    """Stop background processes."""
    return None


@app.command("api")
def stop_api(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force stop the API server."),
    ] = False,
) -> None:
    """Stop the EVOSEAL API server."""
    typer.echo("Stopping EVOSEAL API server...")
    # TODO: Implement API server stop
    typer.echo("API server stop is not yet implemented.")


@app.command("worker")
def stop_worker(
    worker_id: Annotated[
        str | None,
        typer.Argument(help="ID of the worker to stop. Omit to stop all workers."),
    ] = None,
    worker_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Type of worker to stop (seal, openevolve, dgm)."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force stop the worker(s)."),
    ] = False,
) -> None:
    """Stop background worker(s)."""
    if worker_id:
        typer.echo(f"Stopping worker {worker_id}")
    elif worker_type:
        typer.echo(f"Stopping all {worker_type} workers")
    else:
        typer.echo("Stopping all workers")

    # TODO: Implement worker stop
    typer.echo("Worker stop is not yet implemented.")


@app.command("all")
def stop_all(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force stop all processes."),
    ] = False,
) -> None:
    """Stop all EVOSEAL processes."""
    typer.echo("Stopping all EVOSEAL processes...")
    # TODO: Implement stop all
    typer.echo("Stop all is not yet implemented.")


if __name__ == "__main__":
    app()
