"""
EVOSEAL Configuration Settings

This module contains all the configuration settings for the EVOSEAL project.
Supports multiple environments (development, testing, production) with environment variable overrides.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Protocol, TypeVar, cast

from pydantic import BaseModel, Field, root_validator, validator

# Import BaseSettings with proper type checking
if TYPE_CHECKING:
    from pydantic.env_settings import BaseSettings, SettingsSourceCallable
else:
    from pydantic.env_settings import BaseSettings

    # Define a Protocol for type checking
    class SettingsSourceCallableProtocol(Protocol):
        def __call__(self, settings: BaseSettings) -> dict[str, Any]: ...

    SettingsSourceCallable = SettingsSourceCallableProtocol

# Type variable for generic model typing
T = TypeVar("T", bound=BaseModel)

# Re-export Settings for use in type hints
__all__ = ["Settings"]

# Environment settings
ENV = os.getenv("ENV", "development").lower()
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"


class DGMConfig(BaseModel):
    """Configuration for the Darwin Godel Machine component."""

    enabled: bool = Field(True, description="Whether DGM is enabled")
    module_path: str = Field("dgm", description="Path to the DGM module (relative or absolute)")
    max_iterations: int = Field(100, ge=1, description="Maximum number of iterations")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    checkpoint_dir: str = Field("checkpoints/dgm", description="Directory for storing checkpoints")


class OpenEvolveConfig(BaseModel):
    """Configuration for the OpenEvolve component."""

    enabled: bool = Field(True, description="Whether OpenEvolve is enabled")
    module_path: str = Field(
        "openevolve", description="Path to the OpenEvolve module (relative or absolute)"
    )
    population_size: int = Field(50, ge=1, description="Size of the population")
    max_generations: int = Field(100, ge=1, description="Maximum number of generations")
    mutation_rate: float = Field(0.1, ge=0.0, le=1.0, description="Mutation rate")
    checkpoint_dir: str = Field("checkpoints/openevolve", description="Directory for checkpoints")


class SEALConfig(BaseModel):
    """Configuration for the SEAL component."""

    enabled: bool = Field(True, description="Whether SEAL is enabled")
    module_path: str = Field("SEAL", description="Path to the SEAL module (relative or absolute)")
    few_shot_enabled: bool = Field(True, description="Enable few-shot learning")
    knowledge_base_path: str = Field("data/knowledge", description="Path to knowledge base")
    max_context_length: int = Field(4096, description="Maximum context length for the model")
    default_model: str = Field("gpt-4", description="Default model to use")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field("INFO", description="Logging level")
    file: str | None = Field("logs/evoseal.log", description="Log file path")
    max_size_mb: int = Field(10, description="Maximum log file size in MB")
    backup_count: int = Field(5, description="Number of backup logs to keep")
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )


class DatabaseConfig(BaseModel):
    """Database configuration."""

    database_url: str | None = Field(
        default="sqlite:///./evoseal.db",
        env="DATABASE_URL",
        description="Database connection URL. Defaults to SQLite.",
    )
    echo: bool = Field(False, description="Enable SQL query logging")
    pool_size: int = Field(5, description="Connection pool size")
    max_overflow: int = Field(10, description="Maximum overflow for connection pool")


class Settings(BaseSettings):
    """Main settings class that loads and validates configuration."""

    env: str = Field(ENV, description="Current environment")
    debug: bool = Field(ENV == "development", description="Debug mode")

    # Application settings
    app_name: str = "EVOSEAL"
    secret_key: str = Field(..., description="Secret key for cryptographic operations")

    # Component configurations
    dgm: DGMConfig = Field(default_factory=DGMConfig)
    openevolve: OpenEvolveConfig = Field(default_factory=OpenEvolveConfig)
    seal: SEALConfig = Field(default_factory=SEALConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    class Config:
        extra = "forbid"
        validate_assignment = True
        env_nested_delimiter = "__"
        env_file = ".env"
        env_file_encoding = "utf-8"

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> tuple[SettingsSourceCallable, ...]:
            """Customize settings sources to load from JSON files."""
            return (
                init_settings,
                env_settings,
                file_secret_settings,
                json_config_settings_source,
            )

    @classmethod
    def validate_settings(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate settings after loading.

        Args:
            values: Dictionary of field values to validate

        Returns:
            Validated dictionary of field values
        """
        env = values.get("env", "development")
        if isinstance(env, str):
            env = env.lower()
        values["env"] = env
        values["debug"] = values.get("debug", env == "development")

        # Ensure required directories exist
        os.makedirs(BASE_DIR / "logs", exist_ok=True)
        os.makedirs(BASE_DIR / "data/knowledge", exist_ok=True)
        os.makedirs(BASE_DIR / "checkpoints/openevolve", exist_ok=True)

        return values

    # Add root_validator to the class after method definition
    _validate_settings = root_validator(pre=True, allow_reuse=True)(validate_settings)

    @classmethod
    def model_validate(cls, *args: Any, **kwargs: Any) -> Any:
        """Override model_validate to provide type information."""
        return super().model_validate(*args, **kwargs)


def json_config_settings_source(settings: BaseSettings) -> dict[str, Any]:
    """Load settings from JSON config file if it exists.

    Args:
        settings: The settings instance (unused but required by pydantic)

    Returns:
        Dictionary containing the loaded settings
    """
    config_path = CONFIG_DIR / f"{ENV}.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))
    return {}


# Create settings instance
settings = Settings()

# For backward compatibility with direct attribute access
LOG_LEVEL = settings.logging.level
LOG_FILE = settings.logging.file or "logs/evoseal.log"
DGM_CONFIG = settings.dgm.dict()
OPENEVOLVE_CONFIG = settings.openevolve.dict()
SEAL_CONFIG = settings.seal.dict()

# Ensure required directories exist
for directory in ["logs", "data/knowledge", "checkpoints/openevolve"]:
    os.makedirs(BASE_DIR / directory, exist_ok=True)
