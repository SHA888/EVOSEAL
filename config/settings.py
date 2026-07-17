"""
EVOSEAL Configuration Settings

This module contains all the configuration settings for the EVOSEAL project.
Supports multiple environments (development, testing, production) with environment variable overrides.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

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

    model_config = ConfigDict(extra="forbid")

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


class SEALProviderConfig(BaseModel):
    """Configuration for a SEAL provider."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Provider name")
    enabled: bool = Field(True, description="Whether this provider is enabled")
    priority: int = Field(1, description="Provider priority (higher = preferred)")
    config: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific configuration"
    )


class SEALConfig(BaseModel):
    """Configuration for the SEAL component."""

    enabled: bool = Field(
        True, description="Whether SEAL (Self-Adapting Language Models) is enabled"
    )
    module_path: str = Field(
        "SEAL (Self-Adapting Language Models)",
        description="Path to the SEAL (Self-Adapting Language Models) module (relative or absolute)",
    )
    few_shot_enabled: bool = Field(True, description="Enable few-shot learning")
    knowledge_base_path: str = Field("data/knowledge", description="Path to knowledge base")
    max_context_length: int = Field(4096, description="Maximum context length for the model")
    default_model: str = Field("gpt-4", description="Default model to use")

    # Provider configuration
    default_provider: str = Field("ollama", description="Default provider to use")
    # No model is pinned here: OllamaProvider discovers the concrete model from
    # what is installed in Ollama, per role (see evoseal.providers.local_models).
    # This keeps the config durable across model swaps/re-quantizations and avoids
    # importing evoseal.providers from this foundational module (import cycle).
    providers: dict[str, SEALProviderConfig] = Field(
        default_factory=lambda: {
            "ollama": SEALProviderConfig(
                name="ollama",
                enabled=True,
                priority=10,
                config={
                    "base_url": "http://localhost:11434",
                    "role": "coder",
                    "timeout": 90,
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
            ),
            "ollama_reviewer": SEALProviderConfig(
                name="ollama_reviewer",
                enabled=True,
                priority=9,
                config={
                    "base_url": "http://localhost:11434",
                    "role": "reviewer",
                    "timeout": 90,
                    "temperature": 0.3,
                    "max_tokens": 2048,
                },
            ),
            "dummy": SEALProviderConfig(name="dummy", enabled=True, priority=1, config={}),
        },
        description="Available SEAL providers",
    )


class BudgetConfig(BaseModel):
    """Configuration for token budget and cost tracking."""

    model_config = ConfigDict(extra="forbid")

    max_tokens_per_run: int = Field(500_000, ge=1, description="Hard cap on tokens for entire run")
    max_cost_per_run: float | None = Field(
        None, ge=0.0, description="Hard cap on cost (USD) for entire run"
    )
    cost_per_1k_tokens: float = Field(
        0.005, ge=0.0, description="Cost per 1000 tokens for cost calculation"
    )
    warn_at_percent_of_budget: int = Field(
        80, ge=1, le=100, description="Percentage at which to warn about budget consumption"
    )
    stop_on_exhaustion: bool = Field(True, description="Stop cleanly when budget is exhausted")
    stop_tolerance_tokens: int = Field(
        500, ge=0, description="Allow overage up to this amount for in-flight requests"
    )
    max_tokens_per_cycle: int = Field(
        15_000, ge=1, description="Reject any cycle costing more than this"
    )
    max_tokens_per_epoch: int = Field(
        20_000, ge=1, description="Reject fine-tuning checkpoints costing more than this"
    )

    @field_validator("max_tokens_per_cycle")
    @classmethod
    def validate_cycle_budget(cls, v: int, info: Any) -> int:
        """Ensure max_tokens_per_cycle does not exceed max_tokens_per_run."""
        if "max_tokens_per_run" in info.data and v > info.data["max_tokens_per_run"]:
            raise ValueError(
                f"max_tokens_per_cycle ({v}) cannot exceed max_tokens_per_run "
                f"({info.data['max_tokens_per_run']})"
            )
        return v

    @field_validator("max_tokens_per_epoch")
    @classmethod
    def validate_epoch_budget(cls, v: int, info: Any) -> int:
        """Ensure max_tokens_per_epoch does not exceed max_tokens_per_run."""
        if "max_tokens_per_run" in info.data and v > info.data["max_tokens_per_run"]:
            raise ValueError(
                f"max_tokens_per_epoch ({v}) cannot exceed max_tokens_per_run "
                f"({info.data['max_tokens_per_run']})"
            )
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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
    app_name: str = "EVOSEAL"
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for cryptographic operations",
    )
    dgm: DGMConfig = Field(default_factory=DGMConfig)
    openevolve: OpenEvolveConfig = Field(default_factory=OpenEvolveConfig)
    seal: SEALConfig = Field(default_factory=SEALConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="evoseal_",
        from_attributes=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to include JSON config."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            JsonConfigSettingsSource(settings_cls),
        )

    @model_validator(mode="before")
    @classmethod
    def validate_settings(cls, values: Any) -> Any:
        """Validate settings after loading.

        Args:
            values: Raw field values to validate (a mapping for the normal path).

        Returns:
            Validated field values
        """
        # A ``mode="before"`` validator can receive non-dict input; only apply the
        # dict-based production checks when we actually got a mapping.
        if not isinstance(values, dict):
            return values

        # Ensure secret key is set in production
        env = values.get("env", "development")
        if (
            env == "production"
            and values.get("secret_key") == "dev-secret-key-change-in-production"
        ):
            raise ValueError("SECRET_KEY must be set in production")

        # Ensure database URL is set in production
        if env == "production" and not values.get("database", {}).get("database_url"):
            raise ValueError("DATABASE_URL must be set in production")

        return values


class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    """Load settings from JSON config file if it exists."""

    def get_field_value(self, field: Field, field_name: str) -> tuple[Any, str, bool]:
        """Get a field value from the JSON config."""
        config_path = CONFIG_DIR / f"settings.{ENV}.json"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config_data = json.load(f)
                field_value = config_data.get(field_name)
                if field_value is not None:
                    return field_value, field_name, True
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        """Load settings from JSON config file if it exists."""
        config_path = CONFIG_DIR / f"settings.{ENV}.json"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
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
