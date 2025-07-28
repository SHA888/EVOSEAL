"""
Manage EVOSEAL configuration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from ..base import EVOSEALCommand

app = typer.Typer(name="config", help="Manage EVOSEAL configuration")

# Supported configuration formats
CONFIG_FORMATS: dict[str, str] = {"yaml": ".yaml", "json": ".json"}
DEFAULT_FORMAT: str = "yaml"

# Default configuration paths
DEFAULT_PATHS: list[Path] = [
    Path(".evoseal/config.yaml"),
    Path("config/config.yaml"),
    Path("config.yaml"),
]


def find_config_file() -> Path | None:
    """Find the configuration file in standard locations."""
    for path in DEFAULT_PATHS:
        if path.exists():
            return path.resolve()
    return None


def load_config(path: Path) -> dict[str, Any]:
    """Load configuration from a file.

    Args:
        path: Path to the config file.

    Returns:
        The loaded configuration as a dictionary.

    Raises:
        typer.BadParameter: If there's an error loading the config file.
    """
    suffix = path.suffix.lower()
    try:
        with open(path, encoding="utf-8") as f:
            if suffix == ".json":
                config = json.load(f)
                if not isinstance(config, dict):
                    return {"config": config}  # Wrap non-dict configs
                return config
            else:  # Assume YAML for .yaml or .yml
                config = yaml.safe_load(f)
                if config is None:  # Empty YAML file
                    return {}
                if not isinstance(config, dict):
                    return {"config": config}  # Wrap non-dict configs
                return config
    except Exception as e:
        raise typer.BadParameter(f"Error loading config file: {e}") from e


def save_config(config: dict[str, Any], path: Path, fmt: str = DEFAULT_FORMAT) -> None:
    """Save configuration to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "w", encoding="utf-8") as f:
            if fmt == "json":
                json.dump(config, f, indent=2)
            else:  # YAML
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        raise typer.BadParameter(f"Error saving config file: {e}") from e


@app.callback()
def main() -> None:
    """Manage EVOSEAL configuration."""
    return None


@app.command("show")
def show_config(
    key: Annotated[
        str | None,
        typer.Argument(help="Configuration key to show (e.g., 'seal.model'). Omit to show all."),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to config file.",
            dir_okay=False,
            file_okay=True,
            resolve_path=True,
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format (yaml/json).",
            case_sensitive=False,
        ),
    ] = "yaml",
) -> None:
    """Show configuration values.

    Args:
        key: Configuration key to show (e.g., 'seal.model'). Omit to show all.
        config_file: Path to config file.
        format: Output format (yaml/json).
    """
    """Show configuration values."""
    # If no config file is provided, try to find one
    if config_file is None:
        config_file = find_config_file()
        if config_file is None:
            typer.echo("No configuration file found. Use 'evoseal config set' to create one.")
            raise typer.Exit(1)

    config = load_config(config_file)

    if key:
        # Show specific key
        keys = key.split(".")
        value = config
        for k in keys:
            if k not in value:
                raise typer.BadParameter(f"Key not found: {key}")
            value = value[k]

        if format == "json":
            typer.echo(json.dumps(value, indent=2))
        else:
            typer.echo(yaml.dump(value, default_flow_style=False, sort_keys=False))
    elif format == "json":
        typer.echo(json.dumps(config, indent=2))
    else:
        typer.echo(yaml.dump(config, default_flow_style=False, sort_keys=False))


@app.command("set")
def set_config(
    key: Annotated[
        str,
        typer.Argument(help="Configuration key (e.g., 'seal.model')."),
    ],
    value: Annotated[
        str,
        typer.Argument(help="Value to set."),
    ],
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to config file.",
            dir_okay=False,
            file_okay=True,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """Set a configuration value.

    Args:
        key: Configuration key (e.g., 'seal.model').
        value: Value to set.
        config_file: Path to config file.
    """
    """Set a configuration value."""
    if config_file is None:
        config_file = find_config_file() or Path("config.yaml")

    # Load existing config or create a new one if it doesn't exist
    if config_file.exists():
        config = load_config(config_file)
    else:
        config = {}

    # Ensure parent directory exists
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Parse the value (try to convert to appropriate type)
    try:
        # Try to evaluate as Python literal
        import ast

        parsed_value = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        # If not a Python literal, use as string
        parsed_value = value

    # Set the value
    keys = key.split(".")
    current = config
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        elif not isinstance(current[k], dict):
            # Convert non-dict value to dict if needed
            current[k] = {"value": current[k]}
        current = current[k]

    current[keys[-1]] = parsed_value

    # Save the updated config
    save_config(config, config_file)
    typer.echo(f"✅ Set {key} = {value}")


@app.command("unset")
def unset_config(
    key: Annotated[
        str,
        typer.Argument(help="Configuration key to unset (e.g., 'seal.model')."),
    ],
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to config file.",
            dir_okay=False,
            file_okay=True,
            resolve_path=True,
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force unset even if the key doesn't exist.",
        ),
    ] = False,
) -> None:
    """Unset a configuration value.

    Args:
        key: Configuration key to unset (e.g., 'seal.model').
        config_file: Path to config file.
        force: Force unset even if the key doesn't exist.
    """
    if config_file is None:
        config_file = find_config_file()
        if config_file is None:
            if not force:
                typer.echo("No configuration file found.")
                raise typer.Exit(1)
            typer.echo("No configuration file found. Nothing to unset.")
            return

    # Load existing config
    if not config_file.exists():
        if not force:
            raise typer.BadParameter(f"Configuration file not found: {config_file}")
        typer.echo(f"Configuration file not found: {config_file}")
        raise typer.Exit(1)

    config = load_config(config_file)

    # Unset the value if it exists
    keys = key.split(".")
    current = config
    for k in keys[:-1]:
        if k not in current:
            if not force:
                raise typer.BadParameter(f"Configuration key not found: {key}")
            typer.echo(f"Configuration key not found: {key}")
            raise typer.Exit(1)
        current = current[k]

    if keys[-1] not in current:
        if not force:
            raise typer.BadParameter(f"Configuration key not found: {key}")
        typer.echo(f"Configuration key not found: {key}")
        raise typer.Exit(1)

    # Remove the key
    del current[keys[-1]]

    # Clean up empty dictionaries
    if not current and len(keys) > 1:
        parent = config
        for k in keys[:-2]:  # Go up two levels to clean up empty parents
            if k in parent:
                parent = parent[k]
        if keys[-2] in parent:
            del parent[keys[-2]]

    # Save the updated config
    save_config(config, config_file)
    typer.echo(f"✅ Unset {key}")


if __name__ == "__main__":
    app()
