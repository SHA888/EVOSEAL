"""
Configuration Utilities

This module provides utilities for loading and managing configuration settings.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.
    
    Args:
        file_path: Path to the YAML configuration file
        
    Returns:
        Dictionary containing the configuration
    """
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML configuration: {str(e)}")

def get_config() -> Dict[str, Any]:
    """
    Get the application configuration.
    
    Returns:
        Dictionary containing the application configuration
    """
    # Load base configuration
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.py"
    config = {}
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            exec(f.read(), {}, config)
    
    # Filter out Python built-ins and imported modules
    config = {k: v for k, v in config.items() if not k.startswith('__')}
    
    return config

def update_config(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update the configuration with new values.
    
    Args:
        new_config: Dictionary containing new configuration values
        
    Returns:
        Updated configuration dictionary
    """
    config = get_config()
    config.update(new_config)
    return config
