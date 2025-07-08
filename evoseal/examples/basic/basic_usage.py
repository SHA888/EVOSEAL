#!/usr/bin/env python3
"""
Basic EVOSEAL CLI Usage Example

This script demonstrates how to use the EVOSEAL CLI programmatically
for a simple evolutionary optimization task.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from typer.testing import CliRunner

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the CLI app after modifying sys.path
from evoseal.cli.main import app  # noqa: E402

# Initialize the CLI test runner
runner = CliRunner()


def run_command(command: list[str], input_text: str | None = None) -> tuple[int, str]:
    """Run a CLI command and return the exit code and output.

    Args:
        command: List of command line arguments
        input_text: Optional input text to pass to the command

    Returns:
        A tuple of (exit_code, output)
    """
    result = runner.invoke(app, command, input=input_text)
    return result.exit_code, str(result.output)


def setup_project(project_dir: str) -> None:
    """Set up a new EVOSEAL project."""
    typer.echo(f"Setting up EVOSEAL project in {project_dir}...")
    project_path = Path(project_dir)

    # Create project directory if it doesn't exist
    project_path.mkdir(parents=True, exist_ok=True)

    # Initialize the project
    exit_code, output = run_command(["init", "project", project_dir])
    if exit_code != 0:
        typer.echo(f"Failed to initialize project: {output}")
        raise typer.Exit(1)

    typer.echo("✅ Project setup complete")


def configure_project(project_dir: str) -> None:
    """Configure the EVOSEAL project."""
    typer.echo("Configuring project...")
    project_path = Path(project_dir)

    # Example configuration
    config_updates = {
        "seal.model": "gpt-4",
        "seal.temperature": "0.7",
        "openevolve.population_size": "10",
        "openevolve.generations": "5",
    }

    for key, value in config_updates.items():
        config_path = str(project_path / ".evoseal" / "config.yaml")
        exit_code, output = run_command(["config", "set", key, value, "--config", config_path])
        if exit_code != 0:
            typer.echo(f"Failed to set {key}: {output}")
            raise typer.Exit(1)

    typer.echo("✅ Project configuration complete")


def run_evolution(project_dir: str) -> None:
    """Run an evolutionary optimization task."""
    typer.echo("Running evolutionary optimization...")

    # Run the evolution
    exit_code, output = run_command(["openevolve", "run", "--project-dir", project_dir])
    if exit_code != 0:
        typer.echo(f"Evolution failed: {output}")
        raise typer.Exit(1)

    typer.echo("✅ Evolution complete")


def analyze_results(project_dir: str) -> None:
    """Analyze the results of the evolution."""
    typer.echo("Analyzing results...")
    project_path = Path(project_dir)

    # Get evolution status
    exit_code, output = run_command(["openevolve", "status", "--project-dir", project_dir])
    typer.echo(output)

    # Export results
    results_file = str(project_path / "results.json")
    exit_code, output = run_command(
        ["export", "results", "--output", results_file, "--project-dir", project_dir]
    )
    if exit_code != 0:
        typer.echo(f"Failed to export results: {output}")
        raise typer.Exit(1)

    typer.echo(f"✅ Results exported to {results_file}")


# Default project directory for the CLI argument
DEFAULT_PROJECT_DIR = "evoseal_project"


def main(project_dir: str = typer.Argument(DEFAULT_PROJECT_DIR, help="Project directory")) -> None:
    """Run a complete EVOSEAL workflow example."""
    # Run the workflow
    setup_project(project_dir)
    configure_project(project_dir)
    run_evolution(project_dir)
    analyze_results(project_dir)

    typer.echo("\n🎉 EVOSEAL workflow completed successfully! 🎉")
    typer.echo(f"Project directory: {project_dir}")


if __name__ == "__main__":
    typer.run(main)
