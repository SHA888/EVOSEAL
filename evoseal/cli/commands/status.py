"""
Show system status for the EVOSEAL CLI.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from ..base import EVOSEALCommand

# Initialize the Typer app
app = typer.Typer(name="status", help="Show system status")


@app.callback()
def main() -> None:
    """Show system status."""
    return None


@app.command("api")
def api_status(
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (text, json)."),
    ] = "text",
) -> None:
    """Show API server status."""
    status_info = {
        "service": "API Server",
        "status": "unknown",
        "endpoints": [],
        "uptime": "0s",
    }

    # TODO: Implement actual API status check

    if format == "json":
        typer.echo(json.dumps(status_info, indent=2))
    else:
        typer.echo(f"Service: {status_info['service']}")
        typer.echo(f"Status: {status_info['status']}")
        typer.echo(f"Uptime: {status_info['uptime']}")
        if status_info["endpoints"]:
            typer.echo("Endpoints:")
            for endpoint in status_info["endpoints"]:
                typer.echo(f"  - {endpoint}")


@app.command("worker")
def worker_status(
    worker_id: Annotated[
        str | None,
        typer.Argument(help="ID of the worker to check. Omit to show all workers."),
    ] = None,
    worker_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter workers by type (seal, openevolve, dgm)."),
    ] = None,
) -> None:
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (text, json)."),
    ] = "text"
    """Show worker status."""
    # TODO: Implement actual worker status check
    workers: list[dict[str, Any]] = [
        {
            "id": "worker-1",
            "type": "seal",
            "status": "running",
            "started": "2025-06-21T10:00:00Z",
            "processed": 42,
        },
        {
            "id": "worker-2",
            "type": "openevolve",
            "status": "idle",
            "started": "2025-06-21T10:05:00Z",
            "processed": 0,
        },
    ]

    # Filter workers if needed
    if worker_id:
        workers = [w for w in workers if w["id"] == worker_id]
    if worker_type:
        workers = [w for w in workers if w["type"] == worker_type]

    if format == "json":
        typer.echo(json.dumps(workers, indent=2))
    else:
        if not workers:
            typer.echo("No workers found matching the criteria.")
            return

        for worker in workers:
            typer.echo(f"Worker {worker['id']} ({worker['type']}):")
            typer.echo(f"  Status: {worker['status']}")
            typer.echo(f"  Started: {worker['started']}")
            typer.echo(f"  Processed: {worker['processed']} tasks")
            typer.echo()


@app.command("system")
def system_status(
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format (text, json)."),
    ] = "text",
) -> None:
    """Show overall system status."""
    import os
    from pathlib import Path

    import psutil

    # Check for pipeline state
    pipeline_state_file = ".evoseal/pipeline_state.json"
    pipeline_status = "not_initialized"
    pipeline_info = {}

    if os.path.exists(pipeline_state_file):
        try:
            with open(pipeline_state_file, 'r') as f:
                pipeline_info = json.load(f)
                pipeline_status = pipeline_info.get("status", "unknown")
        except (json.JSONDecodeError, FileNotFoundError):
            pipeline_status = "error"

    # Get system resources
    try:
        cpu_percent = psutil.cpu_percent(interval=1) / 100.0
        memory = psutil.virtual_memory()
        memory_percent = memory.percent / 100.0
        disk = psutil.disk_usage('.')
        disk_percent = disk.used / disk.total
    except:
        cpu_percent = 0.0
        memory_percent = 0.0
        disk_percent = 0.0

    # Component status based on actual checks
    components = [
        {"name": "Evolution Pipeline", "status": pipeline_status},
        {"name": "API Server", "status": "stopped"},  # TODO: Check actual API status
        {
            "name": "SEAL (Self-Adapting Language Models) Worker",
            "status": "idle",
        },  # TODO: Check actual worker status
        {"name": "Evolve Worker", "status": "idle"},  # TODO: Check actual worker status
        {"name": "DGM Worker", "status": "idle"},  # TODO: Check actual worker status
    ]

    status_info: dict[str, Any] = {
        "version": "0.1.0",
        "status": "operational" if pipeline_status != "failed" else "degraded",
        "pipeline": {
            "status": pipeline_status,
            "current_iteration": pipeline_info.get("current_iteration", 0),
            "total_iterations": pipeline_info.get("total_iterations", 0),
            "current_stage": pipeline_info.get("current_stage"),
        },
        "components": components,
        "resources": {
            "cpu": round(cpu_percent, 3),
            "memory": round(memory_percent, 3),
            "disk": round(disk_percent, 3),
        },
    }

    if format == "json":
        typer.echo(json.dumps(status_info, indent=2))
    else:
        typer.echo(f"EVOSEAL v{status_info['version']}")
        typer.echo(f"Status: {status_info['status'].upper()}")

        # Pipeline status
        pipeline = status_info.get("pipeline", {})
        if pipeline:
            typer.echo("\nPipeline:")
            typer.echo(f"  Status: {pipeline.get('status', 'unknown').upper()}")
            if pipeline.get('current_iteration') is not None:
                typer.echo(
                    f"  Progress: {pipeline.get('current_iteration', 0)}/{pipeline.get('total_iterations', 0)} iterations"
                )
            if pipeline.get('current_stage'):
                typer.echo(f"  Current Stage: {pipeline.get('current_stage')}")

        typer.echo("\nComponents:")
        for component in status_info["components"]:
            status_color = (
                "🟢"
                if component['status'] in ['running', 'operational']
                else "🔴" if component['status'] in ['failed', 'error'] else "🟡"
            )
            typer.echo(f"  {status_color} {component['name']}: {component['status'].upper()}")

        typer.echo("\nResource Usage:")
        resources = status_info["resources"]
        typer.echo(f"  CPU: {resources['cpu']*100:.1f}%")
        typer.echo(f"  Memory: {resources['memory']*100:.1f}%")
        typer.echo(f"  Disk: {resources['disk']*100:.1f}%")


if __name__ == "__main__":
    app()
