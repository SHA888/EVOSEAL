"""
Pipeline control commands for the EVOSEAL CLI.

This module provides comprehensive pipeline control functionality including
initialization, execution control, status monitoring, and debugging options.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Annotated, Any, Dict, Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from ..base import EVOSEALCommand

# Initialize the Typer app
app = typer.Typer(name="pipeline", help="Pipeline control and monitoring")

# Global console for rich output
console = Console()

# Pipeline state file location
PIPELINE_STATE_FILE = ".evoseal/pipeline_state.json"
PIPELINE_CONFIG_FILE = ".evoseal/pipeline_config.json"
PIPELINE_LOG_FILE = ".evoseal/pipeline.log"


class PipelineState:
    """Manages pipeline state persistence."""

    def __init__(self, state_file: str = PIPELINE_STATE_FILE):
        self.state_file = state_file
        self.ensure_state_dir()

    def ensure_state_dir(self):
        """Ensure the state directory exists."""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

    def load_state(self) -> Dict[str, Any]:
        """Load pipeline state from file."""
        if not os.path.exists(self.state_file):
            return {
                "status": "not_started",
                "current_iteration": 0,
                "total_iterations": 0,
                "start_time": None,
                "pause_time": None,
                "current_stage": None,
                "progress": {},
                "config": {},
            }

        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return self.load_state()  # Return default state

    def save_state(self, state: Dict[str, Any]):
        """Save pipeline state to file."""
        self.ensure_state_dir()
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def update_state(self, updates: Dict[str, Any]):
        """Update specific fields in the state."""
        state = self.load_state()
        state.update(updates)
        self.save_state(state)


class PipelineConfig:
    """Manages pipeline configuration."""

    def __init__(self, config_file: str = PIPELINE_CONFIG_FILE):
        self.config_file = config_file
        self.ensure_config_dir()

    def ensure_config_dir(self):
        """Ensure the config directory exists."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

    def load_config(self) -> Dict[str, Any]:
        """Load pipeline configuration."""
        if not os.path.exists(self.config_file):
            return self.get_default_config()

        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return self.get_default_config()

    def save_config(self, config: Dict[str, Any]):
        """Save pipeline configuration."""
        self.ensure_config_dir()
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

    def get_default_config(self) -> Dict[str, Any]:
        """Get default pipeline configuration."""
        return {
            "iterations": 10,
            "auto_checkpoint": True,
            "checkpoint_interval": 5,
            "auto_rollback": True,
            "regression_threshold": 0.05,
            "components": {
                "dgm": {"enabled": True, "timeout": 300},
                "openevolve": {"enabled": True, "timeout": 600},
                "seal": {"enabled": True, "timeout": 300},
            },
            "logging": {"level": "INFO", "file": PIPELINE_LOG_FILE, "console": True},
            "monitoring": {"progress_update_interval": 1.0, "metrics_collection": True},
        }


# Global instances
pipeline_state = PipelineState()
pipeline_config = PipelineConfig()


@app.callback()
def main() -> None:
    """Pipeline control and monitoring commands."""
    return None


@app.command("init")
def init_pipeline(
    repository: Annotated[
        str, typer.Argument(help="Repository URL or path to initialize pipeline for")
    ],
    config_file: Annotated[
        Optional[str], typer.Option("--config", "-c", help="Path to configuration file")
    ] = None,
    iterations: Annotated[
        int, typer.Option("--iterations", "-i", help="Number of evolution iterations")
    ] = 10,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Force initialization even if pipeline exists")
    ] = False,
) -> None:
    """Initialize a new evolution pipeline for a repository."""

    # Check if pipeline already exists
    if os.path.exists(PIPELINE_STATE_FILE) and not force:
        console.print("[yellow]Pipeline already exists. Use --force to reinitialize.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[blue]Initializing evolution pipeline for: {repository}[/blue]")

    # Load or create configuration
    config = pipeline_config.load_config()
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            user_config = json.load(f)
            config.update(user_config)

    # Update iterations if specified
    config["iterations"] = iterations

    # Initialize pipeline state
    initial_state = {
        "status": "initialized",
        "repository": repository,
        "current_iteration": 0,
        "total_iterations": iterations,
        "start_time": None,
        "pause_time": None,
        "current_stage": None,
        "progress": {
            "stages_completed": 0,
            "total_stages": 7,  # Standard pipeline stages
            "current_stage_progress": 0.0,
        },
        "config": config,
    }

    # Save configuration and state
    pipeline_config.save_config(config)
    pipeline_state.save_state(initial_state)

    # Setup logging
    setup_logging(config.get("logging", {}))

    console.print("[green]✓ Pipeline initialized successfully[/green]")
    console.print(f"[dim]Configuration saved to: {PIPELINE_CONFIG_FILE}[/dim]")
    console.print(f"[dim]State file: {PIPELINE_STATE_FILE}[/dim]")

    # Show configuration summary
    show_config_summary(config)


@app.command("start")
def start_pipeline(
    resume: Annotated[
        bool, typer.Option("--resume", "-r", help="Resume from last checkpoint")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", "-d", help="Enable debug mode")] = False,
    interactive: Annotated[
        bool, typer.Option("--interactive", "-i", help="Enable interactive debugging")
    ] = False,
) -> None:
    """Start the evolution pipeline."""

    state = pipeline_state.load_state()

    if state["status"] == "not_started":
        console.print("[red]Pipeline not initialized. Run 'evoseal pipeline init' first.[/red]")
        raise typer.Exit(1)

    if state["status"] == "running":
        console.print("[yellow]Pipeline is already running.[/yellow]")
        raise typer.Exit(1)

    # Update state
    pipeline_state.update_state(
        {
            "status": "running",
            "start_time": time.time(),
            "pause_time": None,
            "debug_mode": debug,
            "interactive_mode": interactive,
        }
    )

    console.print("[green]🚀 Starting evolution pipeline...[/green]")

    if debug:
        console.print("[yellow]Debug mode enabled[/yellow]")

    if interactive:
        console.print("[yellow]Interactive debugging enabled[/yellow]")

    # Start the pipeline execution
    try:
        asyncio.run(run_pipeline_async(state, debug, interactive))
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user[/yellow]")
        pipeline_state.update_state({"status": "paused", "pause_time": time.time()})
    except Exception as e:
        console.print(f"[red]Pipeline failed: {str(e)}[/red]")
        pipeline_state.update_state({"status": "failed", "error": str(e)})
        raise typer.Exit(1)


@app.command("pause")
def pause_pipeline() -> None:
    """Pause the running pipeline."""

    state = pipeline_state.load_state()

    if state["status"] != "running":
        console.print("[yellow]No running pipeline to pause.[/yellow]")
        raise typer.Exit(1)

    pipeline_state.update_state({"status": "paused", "pause_time": time.time()})

    console.print("[yellow]⏸️  Pipeline paused[/yellow]")


@app.command("resume")
def resume_pipeline() -> None:
    """Resume a paused pipeline."""

    state = pipeline_state.load_state()

    if state["status"] != "paused":
        console.print("[yellow]No paused pipeline to resume.[/yellow]")
        raise typer.Exit(1)

    pipeline_state.update_state({"status": "running", "pause_time": None})

    console.print("[green]▶️  Pipeline resumed[/green]")

    # Continue execution
    try:
        asyncio.run(
            run_pipeline_async(
                state, state.get("debug_mode", False), state.get("interactive_mode", False)
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user[/yellow]")
        pipeline_state.update_state({"status": "paused", "pause_time": time.time()})


@app.command("stop")
def stop_pipeline(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Force stop without cleanup")
    ] = False,
) -> None:
    """Stop the pipeline execution."""

    state = pipeline_state.load_state()

    if state["status"] not in ["running", "paused"]:
        console.print("[yellow]No active pipeline to stop.[/yellow]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm("Are you sure you want to stop the pipeline?")
        if not confirm:
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    pipeline_state.update_state({"status": "stopped", "stop_time": time.time()})

    console.print("[red]⏹️  Pipeline stopped[/red]")


@app.command("status")
def show_status(
    detailed: Annotated[
        bool, typer.Option("--detailed", "-d", help="Show detailed status information")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output status as JSON")] = False,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Watch status in real-time")] = False,
) -> None:
    """Show pipeline status and progress."""

    if watch:
        watch_pipeline_status(detailed)
        return

    state = pipeline_state.load_state()

    if json_output:
        console.print(json.dumps(state, indent=2))
        return

    display_pipeline_status(state, detailed)


@app.command("config")
def manage_config(
    show: Annotated[bool, typer.Option("--show", "-s", help="Show current configuration")] = False,
    edit: Annotated[
        bool, typer.Option("--edit", "-e", help="Edit configuration interactively")
    ] = False,
    set_param: Annotated[
        Optional[str], typer.Option("--set", help="Set configuration parameter (key=value)")
    ] = None,
    reset: Annotated[bool, typer.Option("--reset", help="Reset to default configuration")] = False,
) -> None:
    """Manage pipeline configuration."""

    if reset:
        config = pipeline_config.get_default_config()
        pipeline_config.save_config(config)
        console.print("[green]Configuration reset to defaults[/green]")
        return

    if set_param:
        if "=" not in set_param:
            console.print("[red]Invalid format. Use key=value[/red]")
            raise typer.Exit(1)

        key, value = set_param.split("=", 1)
        config = pipeline_config.load_config()

        # Try to parse value as JSON for complex types
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass  # Keep as string

        # Set nested keys
        keys = key.split(".")
        current = config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

        pipeline_config.save_config(config)
        console.print(f"[green]Set {key} = {value}[/green]")
        return

    config = pipeline_config.load_config()

    if edit:
        # TODO: Implement interactive configuration editing
        console.print("[yellow]Interactive editing not yet implemented[/yellow]")
        console.print(f"[dim]Edit configuration file directly: {PIPELINE_CONFIG_FILE}[/dim]")

    if show or not any([edit, set_param, reset]):
        show_config_summary(config)


@app.command("logs")
def show_logs(
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="Follow log output in real-time")
    ] = False,
    lines: Annotated[int, typer.Option("--lines", "-n", help="Number of lines to show")] = 50,
    level: Annotated[
        Optional[str], typer.Option("--level", "-l", help="Filter by log level")
    ] = None,
) -> None:
    """Show pipeline logs."""

    if not os.path.exists(PIPELINE_LOG_FILE):
        console.print("[yellow]No log file found[/yellow]")
        return

    if follow:
        # TODO: Implement log following
        console.print("[yellow]Log following not yet implemented[/yellow]")
        console.print(f"[dim]Use: tail -f {PIPELINE_LOG_FILE}[/dim]")
        return

    try:
        with open(PIPELINE_LOG_FILE, 'r') as f:
            log_lines = f.readlines()

        # Show last N lines
        display_lines = log_lines[-lines:] if lines > 0 else log_lines

        for line in display_lines:
            line = line.strip()
            if level and level.upper() not in line:
                continue

            # Color code log levels
            if "ERROR" in line:
                console.print(f"[red]{line}[/red]")
            elif "WARNING" in line:
                console.print(f"[yellow]{line}[/yellow]")
            elif "INFO" in line:
                console.print(f"[blue]{line}[/blue]")
            elif "DEBUG" in line:
                console.print(f"[dim]{line}[/dim]")
            else:
                console.print(line)

    except Exception as e:
        console.print(f"[red]Error reading log file: {e}[/red]")


@app.command("debug")
def debug_pipeline(
    breakpoint: Annotated[
        Optional[str], typer.Option("--breakpoint", "-b", help="Set breakpoint at stage")
    ] = None,
    inspect: Annotated[
        bool, typer.Option("--inspect", "-i", help="Inspect current pipeline state")
    ] = False,
    step: Annotated[
        bool, typer.Option("--step", "-s", help="Enable step-by-step execution")
    ] = False,
) -> None:
    """Interactive debugging options for the pipeline."""

    state = pipeline_state.load_state()

    if inspect:
        display_debug_info(state)
        return

    if breakpoint:
        # TODO: Implement breakpoint functionality
        console.print(f"[yellow]Setting breakpoint at: {breakpoint}[/yellow]")
        console.print("[yellow]Breakpoint functionality not yet implemented[/yellow]")
        return

    if step:
        # TODO: Implement step-by-step execution
        console.print("[yellow]Step-by-step execution not yet implemented[/yellow]")
        return

    console.print("[blue]Debug options:[/blue]")
    console.print("  --inspect    Inspect current pipeline state")
    console.print("  --breakpoint Set breakpoint at specific stage")
    console.print("  --step       Enable step-by-step execution")


# Helper functions


def setup_logging(logging_config: Dict[str, Any]):
    """Setup logging configuration."""
    level = getattr(logging, logging_config.get("level", "INFO").upper())

    # Create logger
    logger = logging.getLogger("evoseal.pipeline")
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers.clear()

    # File handler
    if logging_config.get("file"):
        os.makedirs(os.path.dirname(logging_config["file"]), exist_ok=True)
        file_handler = logging.FileHandler(logging_config["file"])
        file_handler.setLevel(level)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Console handler
    if logging_config.get("console", True):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)


def show_config_summary(config: Dict[str, Any]):
    """Display configuration summary."""
    table = Table(title="Pipeline Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Flatten config for display
    def flatten_dict(d, parent_key="", sep="."):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, str(v)))
        return dict(items)

    flat_config = flatten_dict(config)
    for key, value in flat_config.items():
        table.add_row(key, value)

    console.print(table)


def display_pipeline_status(state: Dict[str, Any], detailed: bool = False):
    """Display pipeline status information."""
    status = state.get("status", "unknown")

    # Status panel
    status_color = {
        "not_started": "dim",
        "initialized": "blue",
        "running": "green",
        "paused": "yellow",
        "stopped": "red",
        "completed": "green",
        "failed": "red",
    }.get(status, "dim")

    status_panel = Panel(
        f"[{status_color}]{status.upper()}[/{status_color}]", title="Pipeline Status", expand=False
    )
    console.print(status_panel)

    # Basic information
    info_table = Table(show_header=False)
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value", style="white")

    if state.get("repository"):
        info_table.add_row("Repository", state["repository"])

    info_table.add_row(
        "Current Iteration",
        f"{state.get('current_iteration', 0)}/{state.get('total_iterations', 0)}",
    )

    if state.get("current_stage"):
        info_table.add_row("Current Stage", state["current_stage"])

    if state.get("start_time"):
        start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state["start_time"]))
        info_table.add_row("Started", start_time)

    console.print(info_table)

    # Progress information
    progress_info = state.get("progress", {})
    if progress_info:
        progress_table = Table(title="Progress")
        progress_table.add_column("Metric", style="cyan")
        progress_table.add_column("Value", style="green")

        for key, value in progress_info.items():
            progress_table.add_row(key.replace("_", " ").title(), str(value))

        console.print(progress_table)

    # Detailed information
    if detailed:
        if state.get("config"):
            console.print("\n[bold]Configuration:[/bold]")
            show_config_summary(state["config"])


def display_debug_info(state: Dict[str, Any]):
    """Display debug information about the pipeline."""
    console.print("[bold blue]Pipeline Debug Information[/bold blue]")

    # State information
    debug_table = Table(title="Debug State")
    debug_table.add_column("Property", style="cyan")
    debug_table.add_column("Value", style="white")

    debug_table.add_row("State File", PIPELINE_STATE_FILE)
    debug_table.add_row("Config File", PIPELINE_CONFIG_FILE)
    debug_table.add_row("Log File", PIPELINE_LOG_FILE)
    debug_table.add_row("Debug Mode", str(state.get("debug_mode", False)))
    debug_table.add_row("Interactive Mode", str(state.get("interactive_mode", False)))

    console.print(debug_table)

    # Full state dump
    console.print("\n[bold]Full State:[/bold]")
    console.print(json.dumps(state, indent=2))


def watch_pipeline_status(detailed: bool = False):
    """Watch pipeline status in real-time."""
    console.print("[blue]Watching pipeline status... (Press Ctrl+C to exit)[/blue]")

    try:
        while True:
            console.clear()
            state = pipeline_state.load_state()
            display_pipeline_status(state, detailed)
            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped watching[/yellow]")


async def run_pipeline_async(state: Dict[str, Any], debug: bool = False, interactive: bool = False):
    """Run the pipeline asynchronously with progress visualization."""

    config = state.get("config", {})
    total_iterations = state.get("total_iterations", 10)
    start_iteration = state.get("current_iteration", 0)

    # Create progress display
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        console=console,
    )

    with Live(progress, console=console, refresh_per_second=4):
        # Main iteration task
        iteration_task = progress.add_task("[green]Evolution Iterations", total=total_iterations)

        # Stage task
        stage_task = progress.add_task("[blue]Current Stage", total=7)  # Number of pipeline stages

        # Update progress to current state
        progress.update(iteration_task, completed=start_iteration)

        for iteration in range(start_iteration, total_iterations):
            # Update iteration progress
            progress.update(iteration_task, completed=iteration)
            pipeline_state.update_state({"current_iteration": iteration})

            # Simulate pipeline stages
            stages = [
                "Initializing",
                "Analyzing Code",
                "Generating Improvements",
                "Adapting with SEAL (Self-Adapting Language Models)",
                "Testing Changes",
                "Validating Results",
                "Finalizing",
            ]

            for stage_idx, stage_name in enumerate(stages):
                progress.update(stage_task, description=f"[blue]{stage_name}", completed=stage_idx)
                pipeline_state.update_state({"current_stage": stage_name})

                # Simulate stage work
                await asyncio.sleep(1)

                # Interactive debugging
                if interactive and debug:
                    console.print(f"\n[yellow]Paused at stage: {stage_name}[/yellow]")
                    action = typer.prompt("Continue (c), Skip (s), or Quit (q)?", default="c")
                    if action.lower() == 'q':
                        return
                    elif action.lower() == 's':
                        break

            progress.update(stage_task, completed=7)

            # Check for pause/stop
            current_state = pipeline_state.load_state()
            if current_state["status"] == "paused":
                console.print("\n[yellow]Pipeline paused[/yellow]")
                return
            elif current_state["status"] == "stopped":
                console.print("\n[red]Pipeline stopped[/red]")
                return

        # Complete
        progress.update(iteration_task, completed=total_iterations)
        pipeline_state.update_state(
            {
                "status": "completed",
                "current_iteration": total_iterations,
                "completion_time": time.time(),
            }
        )

        console.print("\n[green]🎉 Pipeline completed successfully![/green]")


if __name__ == "__main__":
    app()
