"""
Provider Manager for EVOSEAL SEAL providers.
Handles provider selection, instantiation, and management.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any

from config.settings import settings
from evoseal.providers.ollama_provider import OllamaProvider
from evoseal.providers.seal_providers import SEALProvider

logger = logging.getLogger(__name__)


def _run_coro_sync(coro, executor=None, timeout=30):  # type: ignore[no-untyped-def]
    """Run *coro* synchronously, even from inside a running event loop.

    When no event loop is running, ``asyncio.run`` is used directly.  When
    called from within a running loop (e.g. an async handler), the coroutine
    is executed in a background thread with its own event loop to avoid the
    ``asyncio.run() cannot be called from a running event loop`` error.

    **Note:** the caller *is* blocked in both branches (``.result()`` waits
    for the background thread to finish).  This is a synchronous bridge
    intended for code paths that genuinely cannot be made async.

    Caveat: each call (without a shared *executor*) creates a fresh event
    loop in a new thread.  If a coroutine caches loop-bound resources
    (e.g. ``aiohttp.ClientSession``) across invocations, those resources
    would be bound to different loops.  Current ``health_check()``
    implementations create fresh sessions per call, so this is safe today
    but worth keeping in mind for future changes.

    Args:
        coro: The coroutine to run.
        executor: Optional shared ``ThreadPoolExecutor``.  When *None*, a
            new single-thread executor is created (and torn down) per call.
        timeout: Maximum seconds to wait for *coro* to complete.  Applied
            via ``asyncio.wait_for`` inside the event loop that runs *coro*.
            Defaults to 30 s.  Set to ``None`` to disable (not recommended).
    """
    if timeout is not None:
        coro = asyncio.wait_for(coro, timeout=timeout)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if executor is not None:
        return executor.submit(asyncio.run, coro).result()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class ProviderManager:
    """Manages SEAL providers and handles provider selection."""

    def __init__(self):
        """Initialize the provider manager."""
        self._providers: dict[str, SEALProvider] = {}
        self._provider_classes: dict[str, type[SEALProvider]] = {
            "ollama": OllamaProvider,
            # Reviewer role runs on the same Ollama backend, different model.
            "ollama_reviewer": OllamaProvider,
        }

        # Import DummySEALProvider if available
        try:
            from evoseal.providers.seal_providers import DummySEALProvider

            self._provider_classes["dummy"] = DummySEALProvider
        except ImportError:
            logger.warning("DummySEALProvider not available")

    def get_provider(self, provider_name: str | None = None) -> SEALProvider:
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

    async def aget_best_available_provider(
        self, *, health_check_timeout: float | None = 30
    ) -> SEALProvider:
        """Async version — await health checks without blocking the event loop.

        Use this instead of :meth:`get_best_available_provider` when already
        inside a coroutine.

        Args:
            health_check_timeout: Per-provider timeout in seconds for
                ``health_check()``.  Defaults to 30.  Set to ``None`` to
                disable (not recommended).

        Returns:
            The best available provider instance

        Raises:
            RuntimeError: If no providers are available
        """
        enabled_providers = [
            (name, config) for name, config in settings.seal.providers.items() if config.enabled
        ]
        if not enabled_providers:
            raise RuntimeError("No SEAL providers are enabled")
        enabled_providers.sort(key=lambda x: x[1].priority, reverse=True)

        for provider_name, provider_config in enabled_providers:
            try:
                provider = self.get_provider(provider_name)
                if hasattr(provider, "health_check"):
                    try:
                        coro = provider.health_check()
                        if health_check_timeout is not None:
                            coro = asyncio.wait_for(coro, timeout=health_check_timeout)
                        is_healthy = await coro
                    except Exception as e:
                        logger.warning(f"Health check failed for {provider_name}: {e}")
                        continue
                    if is_healthy:
                        logger.info(
                            f"Selected provider: {provider_name} "
                            f"(priority: {provider_config.priority})"
                        )
                        return provider
                    else:
                        logger.warning(f"Provider {provider_name} failed health check")
                        continue
                else:
                    logger.info(
                        f"Selected provider: {provider_name} (priority: {provider_config.priority})"
                    )
                    return provider
            except Exception as e:
                logger.warning(f"Failed to initialize provider {provider_name}: {e}")
                continue

        raise RuntimeError("No healthy SEAL providers are available")

    def get_best_available_provider(
        self, *, health_check_timeout: float | None = 30
    ) -> SEALProvider:
        """Get the best available provider based on priority and availability.

        This is the synchronous wrapper — it blocks the calling thread while
        running health checks.  Prefer :meth:`aget_best_available_provider`
        when already inside a coroutine.

        Args:
            health_check_timeout: Per-provider timeout in seconds for
                ``health_check()``.  Defaults to 30.  Set to ``None`` to
                disable (not recommended).

        Returns:
            The best available provider instance

        Raises:
            RuntimeError: If no providers are available
        """
        # Get enabled providers sorted by priority (descending)
        enabled_providers = [
            (name, config) for name, config in settings.seal.providers.items() if config.enabled
        ]

        if not enabled_providers:
            raise RuntimeError("No SEAL providers are enabled")

        # Sort by priority (higher priority first)
        enabled_providers.sort(key=lambda x: x[1].priority, reverse=True)

        # Use a shared executor when running inside an event loop to avoid
        # spinning up a separate thread pool per provider.
        shared_pool: concurrent.futures.ThreadPoolExecutor | None = None
        try:
            asyncio.get_running_loop()
            shared_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        except RuntimeError:
            pass  # No running loop; _run_coro_sync will use asyncio.run directly

        try:
            # Try providers in order of priority
            for provider_name, provider_config in enabled_providers:
                try:
                    provider = self.get_provider(provider_name)

                    # Test provider health if it supports it
                    if hasattr(provider, "health_check"):
                        try:
                            is_healthy = _run_coro_sync(
                                provider.health_check(),
                                executor=shared_pool,
                                timeout=health_check_timeout,
                            )
                        except Exception as e:
                            logger.warning(f"Health check failed for {provider_name}: {e}")
                            continue

                        if is_healthy:
                            logger.info(
                                f"Selected provider: {provider_name} (priority: {provider_config.priority})"
                            )
                            return provider
                        else:
                            logger.warning(f"Provider {provider_name} failed health check")
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
        finally:
            if shared_pool is not None:
                # All futures are already resolved via .result() above, so
                # wait=False is safe — there is nothing left to drain.
                shared_pool.shutdown(wait=False)

    def _create_provider(self, provider_name: str, provider_config: Any) -> SEALProvider:
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
            logger.debug(f"Created {provider_name} provider with config: {config_params}")
            return provider_instance
        except Exception as e:
            logger.error(f"Failed to create {provider_name} provider: {e}")
            raise

    async def alist_providers(
        self, *, health_check_timeout: float | None = 30
    ) -> dict[str, dict[str, Any]]:
        """Async version — await health checks without blocking the event loop.

        Use this instead of :meth:`list_providers` when already inside a
        coroutine.

        Args:
            health_check_timeout: Per-provider timeout in seconds for
                ``health_check()``.  Defaults to 30.  Set to ``None`` to
                disable (not recommended).

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
            if name in self._providers:
                provider = self._providers[name]
                if hasattr(provider, "health_check"):
                    try:
                        coro = provider.health_check()
                        if health_check_timeout is not None:
                            coro = asyncio.wait_for(coro, timeout=health_check_timeout)
                        info["healthy"] = await coro
                    except Exception as e:
                        info["healthy"] = False
                        info["health_error"] = str(e)
                else:
                    info["healthy"] = True
            provider_info[name] = info
        return provider_info

    def list_providers(
        self, *, health_check_timeout: float | None = 30
    ) -> dict[str, dict[str, Any]]:
        """List all configured providers with their status.

        This is the synchronous wrapper — it blocks the calling thread while
        running health checks.  Prefer :meth:`alist_providers` when already
        inside a coroutine.

        Args:
            health_check_timeout: Per-provider timeout in seconds for
                ``health_check()``.  Defaults to 30.  Set to ``None`` to
                disable (not recommended).

        Returns:
            Dictionary with provider information
        """
        provider_info = {}

        # Use a shared executor when running inside an event loop to avoid
        # spinning up a separate thread pool per provider.
        shared_pool: concurrent.futures.ThreadPoolExecutor | None = None
        try:
            asyncio.get_running_loop()
            shared_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        except RuntimeError:
            pass  # No running loop; _run_coro_sync will use asyncio.run directly

        try:
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
                            info["healthy"] = _run_coro_sync(
                                provider.health_check(),
                                executor=shared_pool,
                                timeout=health_check_timeout,
                            )
                        except Exception as e:
                            info["healthy"] = False
                            info["health_error"] = str(e)
                    else:
                        info["healthy"] = True  # Assume healthy if no health check

                provider_info[name] = info
        finally:
            if shared_pool is not None:
                # All futures are already resolved via .result() above, so
                # wait=False is safe — there is nothing left to drain.
                shared_pool.shutdown(wait=False)

        return provider_info

    def reload_providers(self) -> None:
        """Reload provider configuration and clear cached instances."""
        logger.info("Reloading provider configuration")
        self._providers.clear()

    def register_provider_class(self, name: str, provider_class: type[SEALProvider]) -> None:
        """Register a new provider class.

        Args:
            name: Provider name
            provider_class: Provider class
        """
        self._provider_classes[name] = provider_class
        logger.info(f"Registered provider class: {name}")


# Global provider manager instance
provider_manager = ProviderManager()
