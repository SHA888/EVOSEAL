"""
Initialize a new EVOSEAL project.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

# Define the CLI app
app = typer.Typer(name="init", help="Initialize a new EVOSEAL project")

# Template directory structure
TEMPLATE_FILES: dict[str, str] = {
    ".evoseal/config.yaml": """# EVOSEAL Configuration
# This file contains configuration for all EVOSEAL components

# SEAL (Self-Adapting Language Models) Configuration
seal:
  model: "gpt-4"  # Default model
  temperature: 0.7
  max_tokens: 2048

# OpenEvolve Configuration
openevolve:
  population_size: 100
  max_iterations: 1000
  checkpoint_interval: 10

# DGM Configuration
dgm:
  max_generations: 50
  mutation_rate: 0.1
  elitism: 2

# Logging Configuration
logging:
  level: "INFO"
  file: "logs/evoseal.log"
  max_size_mb: 10
  backup_count: 5""",
    ".gitignore": """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Logs
logs/
*.log

# Local development
.env
.venv

# Project specific
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/""",
    "README.md": """# EVOSEAL Project

This is an EVOSEAL project. Edit this file to describe your project.

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure your project in `.evoseal/config.yaml`

3. Start developing!""",
}

# Directory structure to create
DIRECTORIES: list[str] = [
    "src",
    "tests",
    "data/raw",
    "data/processed",
    "notebooks",
    "docs",
    "logs",
]


class ProjectInitializationError(Exception):
    """Custom exception for project initialization errors."""

    pass


@app.command("project")
def init_project(
    project_dir: Annotated[
        Path,
        typer.Argument(
            help="Directory to initialize the project in. Defaults to current directory.",
            file_okay=False,
            dir_okay=True,
            writable=True,
            resolve_path=True,
        ),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force initialization even if directory is not empty.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output.",
        ),
    ] = False,
) -> None:
    """Initialize a new EVOSEAL project in the specified directory.

    Creates the standard EVOSEAL project structure and configuration files.

    Args:
        project_dir: Directory to initialize the project in.
        force: Force initialization even if directory is not empty.
        verbose: Enable verbose output.
    """
    # Track created files and directories for cleanup in case of error
    created_files: list[Path] = []
    created_dirs: list[Path] = []

    # Ensure project_dir is a Path object
    project_dir = Path(str(project_dir))

    try:
        if verbose:
            typer.echo(f"Initializing EVOSEAL project in: {project_dir.absolute()}")

        # Convert to absolute path
        project_dir = project_dir.absolute()

        # Check write permissions
        if not os.access(project_dir.parent, os.W_OK):
            raise ProjectInitializationError(
                f"Insufficient permissions to create directory: {project_dir}"
            )

        # Check if directory is empty or force is enabled
        if project_dir.exists():
            if any(project_dir.iterdir()) and not force:
                raise ProjectInitializationError(
                    f"Directory '{project_dir}' is not empty. " "Use --force to initialize anyway."
                )
        else:
            if verbose:
                typer.echo(f"Creating project directory: {project_dir}")
            project_dir.mkdir(parents=True, exist_ok=True)

        # Create directories
        for dir_path_str in DIRECTORIES:
            dir_path = Path(dir_path_str)
            dir_full_path = project_dir / dir_path
            try:
                dir_full_path.mkdir(parents=True, exist_ok=True)
                (dir_full_path / ".gitkeep").touch()
                created_dirs.append(dir_full_path)
                if verbose:
                    typer.echo(f"Created directory: {dir_full_path}")
            except Exception as e:
                raise ProjectInitializationError(
                    f"Failed to create directory '{dir_full_path}': {str(e)}"
                ) from e

        # Create template files
        for rel_path, content in TEMPLATE_FILES.items():
            file_path = project_dir / rel_path
            try:
                # Ensure parent directory exists
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file content
                file_path.write_text(content)
                created_files.append(file_path)

                if verbose:
                    typer.echo(f"Created file: {file_path}")

            except Exception as e:
                raise ProjectInitializationError(
                    f"Failed to create file '{file_path}': {str(e)}"
                ) from e

        # Create a basic .python-version file if it doesn't exist
        py_version_file = project_dir / ".python-version"
        if not py_version_file.exists():
            try:
                py_version_file.write_text("3.10\n")
                if verbose:
                    typer.echo(f"Created file: {py_version_file}")
            except Exception as e:
                raise ProjectInitializationError(
                    f"Failed to create .python-version file: {str(e)}"
                ) from e

        # Create a basic requirements.txt if it doesn't exist
        requirements_file = project_dir / "requirements.txt"
        if not requirements_file.exists():
            try:
                requirements_file.write_text("# Add your project dependencies here\n")
                if verbose:
                    typer.echo(f"Created file: {requirements_file}")
            except Exception as e:
                raise ProjectInitializationError(
                    f"Failed to create requirements.txt: {str(e)}"
                ) from e

        # Create a basic setup.py if it doesn't exist
        setup_file = project_dir / "setup.py"
        if not setup_file.exists():
            setup_content = """from setuptools import setup, find_packages

setup(
    name="my_evoseal_project",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # Add your project dependencies here
    ],
    python_requires=">=3.9"
)
"""
            try:
                setup_file.write_text(setup_content)
                if verbose:
                    typer.echo("Created setup.py")
            except Exception as e:
                raise ProjectInitializationError(f"Failed to create setup.py: {str(e)}") from e

        # Success message
        success_msg = f"\n✅ Successfully initialized EVOSEAL project in {project_dir}"
        success_msg += "\n\nNext steps:"
        success_msg += "\n  1. Configure your project in '.evoseal/config.yaml'"
        success_msg += "\n  2. Add your source code to the 'src/' directory"
        success_msg += "\n  3. Run 'evoseal --help' to see available commands"
        success_msg += "\n\nHappy coding! 🚀\n"

        typer.echo(success_msg)

    except Exception as e:
        # Clean up on error
        if verbose:
            typer.echo("\nCleaning up due to error...")

        # Remove created files
        for file_path in created_files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    if verbose:
                        typer.echo(f"Removed file: {file_path}")
            except Exception as cleanup_error:
                if verbose:
                    typer.echo(f"Error removing {file_path}: {str(cleanup_error)}")

        # Remove created directories (in reverse order)
        for dir_path in reversed(created_dirs):
            try:
                if isinstance(dir_path, Path) and dir_path.exists():
                    shutil.rmtree(str(dir_path), ignore_errors=True)
                    if verbose:
                        typer.echo(f"Removed directory: {dir_path}")
            except Exception as cleanup_error:
                if verbose:
                    typer.echo(f"Error removing {dir_path}: {str(cleanup_error)}")

        # Re-raise the original exception
        if isinstance(e, ProjectInitializationError):
            raise
        raise ProjectInitializationError(
            f"Unexpected error during project initialization: {str(e)}"
        ) from e


@app.callback()
def main() -> None:
    """Initialize a new EVOSEAL project."""
    return None


if __name__ == "__main__":
    app()
