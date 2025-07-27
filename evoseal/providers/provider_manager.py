"""
Provider Manager for EVOSEAL SEAL providers.
Handles provider selection, instantiation, and management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from config.settings import settings
from evoseal.providers.ollama_provider import OllamaProvider
from evoseal.providers.seal_providers import SEALProvider

logger = logging.getLogger(__name__)


class ProviderManager:
    """Manages SEAL providers and handles provider selection."""

    def __init__(self):
        """Initialize the provider manager."""
        self._providers: Dict[str, SEALProvider] = {}
        self._provider_classes: Dict[str, Type[SEALProvider]] = {
            "ollama": OllamaProvider,
        }

        # Import DummySEALProvider if available
        try:
            from evoseal.providers.seal_providers import DummySEALProvider

            self._provider_classes["dummy"] = DummySEALProvider
        except ImportError:
            logger.warning("DummySEALProvider not available")

    def get_provider(self, provider_name: Optional[str] = None) -> SEALProvider:
        """Get a provider instance by name.

        Args:
            provider_name: Name of the provider to get. If None, uses default.

        Returns:
            The provider instance

        Raises:
            ValueError: If provider is not found or not enabled
        """
        if provider_name is None:
            provider_name = settings.seal.default_provider

        # Check if provider is configured and enabled
        if provider_name not in settings.seal.providers:
            raise ValueError(f"Provider '{provider_name}' is not configured")

        provider_config = settings.seal.providers[provider_name]
        if not provider_config.enabled:
            raise ValueError(f"Provider '{provider_name}' is disabled")

        # Return cached instance if available
        if provider_name in self._providers:
            return self._providers[provider_name]

        # Create new provider instance
        provider_instance = self._create_provider(provider_name, provider_config)
        self._providers[provider_name] = provider_instance

        logger.info(f"Created provider instance: {provider_name}")
        return provider_instance

    def get_best_available_provider(self) -> SEALProvider:
        """Get the best available provider based on priority and availability.

        Returns:
            The best available provider instance

        Raises:
            RuntimeError: If no providers are available
        """
        # Get enabled providers sorted by priority (descending)
        enabled_providers = [
            (name, config)
            for name, config in settings.seal.providers.items()
            if config.enabled
        ]

        if not enabled_providers:
            raise RuntimeError("No SEAL providers are enabled")

        # Sort by priority (higher priority first)
        enabled_providers.sort(key=lambda x: x[1].priority, reverse=True)

        # Try providers in order of priority
        for provider_name, provider_config in enabled_providers:
            try:
                provider = self.get_provider(provider_name)

                # Test provider health if it supports it
                if hasattr(provider, "health_check"):
                    import asyncio

                    try:
                        # Check if we're already in an event loop
                        try:
                            loop = asyncio.get_running_loop()
                            # We're in an event loop, create a task instead
                            task = loop.create_task(provider.health_check())
                            # For now, skip health check in running loop and assume healthy
                            logger.info(
                                f"Skipping health check in running event loop for {provider_name}"
                            )
                            is_healthy = True
                        except RuntimeError:
                            # No running event loop, safe to use asyncio.run
                            is_healthy = asyncio.run(provider.health_check())

                        if is_healthy:
                            logger.info(
                                f"Selected provider: {provider_name} (priority: {provider_config.priority})"
                            )
                            return provider
                        else:
                            logger.warning(
                                f"Provider {provider_name} failed health check"
                            )
                            continue
                    except Exception as e:
                        logger.warning(f"Health check failed for {provider_name}: {e}")
                        continue
                else:
                    # No health check available, assume it's working
                    logger.info(
                        f"Selected provider: {provider_name} (priority: {provider_config.priority})"
                    )
                    return provider

            except Exception as e:
                logger.warning(f"Failed to initialize provider {provider_name}: {e}")
                continue

        raise RuntimeError("No healthy SEAL providers are available")

    def _create_provider(
        self, provider_name: str, provider_config: Any
    ) -> SEALProvider:
        """Create a provider instance.

        Args:
            provider_name: Name of the provider
            provider_config: Provider configuration

        Returns:
            The provider instance

        Raises:
            ValueError: If provider class is not found
        """
        if provider_name not in self._provider_classes:
            raise ValueError(f"Unknown provider class: {provider_name}")

        provider_class = self._provider_classes[provider_name]

        # Extract configuration parameters
        config_params = provider_config.config.copy() if provider_config.config else {}

        # Create provider instance with configuration
        try:
            provider_instance = provider_class(**config_params)
            logger.debug(
                f"Created {provider_name} provider with config: {config_params}"
            )
            return provider_instance
        except Exception as e:
            logger.error(f"Failed to create {provider_name} provider: {e}")
            raise

    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        """List all configured providers with their status.

        Returns:
            Dictionary with provider information
        """
        provider_info = {}

        for name, config in settings.seal.providers.items():
            info = {
                "name": config.name,
                "enabled": config.enabled,
                "priority": config.priority,
                "config": config.config,
                "available": name in self._provider_classes,
                "initialized": name in self._providers,
            }

            # Add health status if provider is initialized
            if name in self._providers:
                provider = self._providers[name]
                if hasattr(provider, "health_check"):
                    try:
                        import asyncio

                        # Check if we're in an event loop
                        try:
                            asyncio.get_running_loop()
                            # Skip health check in running loop
                            info["healthy"] = True
                            info["health_note"] = "Health check skipped (in event loop)"
                        except RuntimeError:
                            info["healthy"] = asyncio.run(provider.health_check())
                    except Exception as e:
                        info["healthy"] = False
                        info["health_error"] = str(e)
                else:
                    info["healthy"] = True  # Assume healthy if no health check

            provider_info[name] = info

        return provider_info

    def reload_providers(self) -> None:
        """Reload provider configuration and clear cached instances."""
        logger.info("Reloading provider configuration")
        self._providers.clear()

    def register_provider_class(
        self, name: str, provider_class: Type[SEALProvider]
    ) -> None:
        """Register a new provider class.

        Args:
            name: Provider name
            provider_class: Provider class
        """
        self._provider_classes[name] = provider_class
        logger.info(f"Registered provider class: {name}")


# Global provider manager instance
provider_manager = ProviderManager()
