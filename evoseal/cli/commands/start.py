"""
Start background processes for the EVOSEAL CLI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(name="start", help="Start background processes")


@app.callback()
def main() -> None:
    """Start background processes."""
    return None


@app.command("api")
def start_api(
    # Note: Binding to 0.0.0.0 exposes the server on all network interfaces.
    # In production, consider using a reverse proxy like Nginx and binding to 127.0.0.1
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind the API server to."),
    ] = "0.0.0.0",  # nosec B104: Binding to all interfaces is intentional for development
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind the API server to."),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload/--no-reload", help="Enable auto-reload."),
    ] = True,
) -> None:
    """Start the EVOSEAL API server."""
    typer.echo(f"Starting EVOSEAL API server on {host}:{port}")
    # TODO: Implement API server startup
    typer.echo("API server is not yet implemented.")


@app.command("worker")
def start_worker(
    worker_type: Annotated[
        str,
        typer.Argument(help="Type of worker to start (seal, openevolve, dgm)."),
    ],
    concurrency: Annotated[
        int,
        typer.Option("--concurrency", "-c", help="Number of worker processes."),
    ] = 1,
) -> None:
    """Start a background worker."""
    typer.echo(f"Starting {worker_type} worker with {concurrency} processes")
    # TODO: Implement worker startup
    typer.echo(f"{worker_type} worker is not yet implemented.")


@app.command("evolution")
def start_evolution(
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Data directory for evolution and training data."),
    ] = None,
    evolution_interval: Annotated[
        int,
        typer.Option(
            "--evolution-interval",
            help="Seconds between evolution cycles.",
        ),
    ] = 3600,
    training_check_interval: Annotated[
        int,
        typer.Option(
            "--training-check-interval",
            help="Seconds between training readiness checks.",
        ),
    ] = 1800,
) -> None:
    """Start the continuous evolution service (research-stage)."""
    typer.echo(
        "Research-stage: the bidirectional co-evolution loop is NOT yet closed — "
        "the daemon currently simulates the evolution leg and does not deploy "
        "fine-tuned weights back to generation. See TODO.md 'Close the bidirectional "
        "co-evolution loop'. Starting the service for development/monitoring only."
    )
    try:
        from evoseal.services.continuous_evolution_service import (
            ContinuousEvolutionService,
        )

        service = ContinuousEvolutionService(
            data_dir=data_dir,
            evolution_interval=evolution_interval,
            training_check_interval=training_check_interval,
        )
        asyncio.run(service.start())
    except KeyboardInterrupt:
        typer.echo("Stopped.")
        raise SystemExit(0)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
