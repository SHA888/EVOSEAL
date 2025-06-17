"""
Logging Utilities

This module provides utilities for configuring and managing logging.
"""
import os
import logging
import logging.config
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

def setup_logging(
    config_path: Optional[str] = None,
    default_level: int = logging.INFO,
    env_key: str = 'LOG_CFG'
) -> None:
    """
    Setup logging configuration from YAML file.
    
    Args:
        config_path: Path to the logging configuration file
        default_level: Default logging level
        env_key: Environment variable that can specify the path to the config file
    """
    if config_path is None:
        # Try to get config path from environment variable
        config_path = os.getenv(env_key, None)
        
    if config_path is None:
        # Use default config path
        config_path = Path(__file__).parent.parent.parent / "config" / "logging.yaml"
    
    config_path = Path(config_path)
    
    if config_path.exists():
        try:
            with open(config_path, 'rt') as f:
                config = yaml.safe_load(f)
                
                # Ensure log directory exists
                log_dir = Path("logs")
                log_dir.mkdir(exist_ok=True)
                
                # Apply config
                logging.config.dictConfig(config)
                
        except Exception as e:
            print(f'Error loading logging config: {e}. Using default config')
            logging.basicConfig(level=default_level)
    else:
        logging.basicConfig(level=default_level)
        logging.warning(f'Logging config file not found at {config_path}. Using default config')

class LoggingMixin:
    """Mixin class that adds logging functionality to other classes."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the logger for the class."""
        self._logger = logging.getLogger(self.__class__.__name__)
        super().__init__(*args, **kwargs)
    
    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger
