"""
EVOSEAL Configuration Module

Provides configuration classes for EVOSEAL components including
providers, fine-tuning, and continuous evolution settings.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SEALProviderConfig(BaseModel):
    """Configuration for SEAL providers."""
    
    name: str = Field(..., description="Provider name")
    priority: int = Field(1, description="Provider priority (higher = preferred)")
    enabled: bool = Field(True, description="Whether provider is enabled")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")


class SEALConfig(BaseSettings):
    """Main EVOSEAL configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="EVOSEAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra environment variables
    )
    
    # Basic settings
    debug: bool = Field(False, description="Enable debug mode")
    log_level: str = Field("INFO", description="Logging level")
    data_dir: Path = Field(Path("data"), description="Data directory")
    
    # Provider settings
    default_provider: str = Field("ollama", description="Default provider name")
    providers: List[SEALProviderConfig] = Field(
        default_factory=lambda: [
            SEALProviderConfig(
                name="ollama",
                priority=10,
                enabled=True,
                config={
                    "base_url": "http://localhost:11434",
                    "model": "devstral:latest",
                    "timeout": 90,
                    "temperature": 0.7
                }
            ),
            SEALProviderConfig(
                name="dummy",
                priority=1,
                enabled=True,
                config={}
            )
        ],
        description="Available providers"
    )
    
    # Evolution settings
    evolution_enabled: bool = Field(True, description="Enable evolution system")
    evolution_interval: int = Field(3600, description="Evolution check interval in seconds")
    min_evolution_samples: int = Field(50, description="Minimum samples for training")
    
    # Fine-tuning settings
    fine_tuning_enabled: bool = Field(True, description="Enable fine-tuning")
    training_check_interval: int = Field(1800, description="Training check interval in seconds")
    model_validation_timeout: int = Field(300, description="Model validation timeout in seconds")
    
    # Monitoring settings
    monitoring_enabled: bool = Field(True, description="Enable monitoring dashboard")
    dashboard_port: int = Field(8081, description="Dashboard port")
    dashboard_host: str = Field("localhost", description="Dashboard host")
    
    def get_provider_config(self, provider_name: str) -> Optional[SEALProviderConfig]:
        """Get configuration for a specific provider."""
        for provider in self.providers:
            if provider.name == provider_name:
                return provider
        return None
    
    def get_enabled_providers(self) -> List[SEALProviderConfig]:
        """Get list of enabled providers sorted by priority."""
        enabled = [p for p in self.providers if p.enabled]
        return sorted(enabled, key=lambda x: x.priority, reverse=True)


# Global configuration instance
config = SEALConfig()
