"""
Configuration Utilities

This module provides utilities for loading and managing configuration settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TypeVar, cast

import yaml

T = TypeVar("T", dict, list, str, int, float, bool, None)
ConfigDict = dict[str, Any]  # Type alias for configuration dictionary


def load_yaml_config(file_path: str | Path) -> ConfigDict:
    """
    Load configuration from a YAML file.

    Args:
        file_path: Path to the YAML configuration file

    Returns:
        Dictionary containing the configuration

    Raises:
        FileNotFoundError: If the configuration file is not found
        yaml.YAMLError: If there's an error parsing the YAML
        ValueError: For other configuration loading errors
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            if not isinstance(config, dict):
                raise ValueError("Configuration file must contain a dictionary")
            return config
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Configuration file not found: {file_path}") from e
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML configuration: {e}") from e


def get_config(config_path: str | Path | None = None) -> ConfigDict:
    """
    Get the application configuration.

    Args:
        config_path: Optional path to the configuration file. If not provided,
                   defaults to 'config/settings.py' in the project root.

    Returns:
        Dictionary containing the application configuration

    Raises:
        FileNotFoundError: If the configuration file is not found
        PermissionError: If there are permission issues reading the file
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "settings.py"
    else:
        config_path = Path(config_path)

    config: ConfigDict = {}

    if not config_path.exists():
        return config

    try:
        with open(config_path, encoding="utf-8") as f:
            exec(f.read(), {}, config)
    except PermissionError as e:
        raise PermissionError(f"Permission denied reading config file: {config_path}") from e
    except Exception as e:
        raise ValueError(f"Error loading configuration from {config_path}: {e}") from e

    # Filter out Python built-ins and imported modules
    return {k: v for k, v in config.items() if not k.startswith("__")}


def update_config(new_config: ConfigDict, config_path: str | Path | None = None) -> ConfigDict:
    """
    Update the configuration with new values.

    Args:
        new_config: Dictionary containing new configuration values
        config_path: Optional path to the configuration file. If not provided,
                   uses the default configuration path.

    Returns:
        Updated configuration dictionary

    Example:
        >>> config = update_config({"DEBUG": True})
        >>> config["DEBUG"]
        True
    """
    config = get_config(config_path)
    config.update(new_config)
    return config


def get_setting(key: str, default: T) -> T:
    """
    Get a specific setting from the configuration.

    Args:
        key: The setting key to retrieve
        default: Default value to return if key is not found

    Returns:
        The value of the setting or the default value if not found

    Example:
        >>> debug_mode = get_setting("DEBUG", False)
    """
    config = get_config()
    value = config.get(key, default)
    return value  # type: ignore[no-any-return]
