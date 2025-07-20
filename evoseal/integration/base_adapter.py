"""
Base Component Adapter for EVOSEAL Integration

This module provides the base interface and common functionality for integrating
external components (DGM, OpenEvolve, SEAL (Self-Adapting Language Models)) into the EVOSEAL pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union

logger = logging.getLogger(__name__)


class ComponentState(Enum):
    """States that a component can be in."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


class ComponentType(Enum):
    """Types of components in the EVOSEAL system."""

    DGM = "dgm"
    OPENEVOLVE = "openevolve"
    SEAL = "seal"


@dataclass
class ComponentConfig:
    """Configuration for a component."""

    component_type: ComponentType
    enabled: bool = True
    timeout: int = 300
    max_retries: int = 3
    retry_delay: float = 1.0
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentStatus:
    """Status information for a component."""

    state: ComponentState
    message: str = ""
    last_updated: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ComponentResult:
    """Result from a component operation."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0


class ComponentLifecycle(Protocol):
    """Protocol for component lifecycle management."""

    async def initialize(self) -> bool:
        """Initialize the component."""
        ...

    async def start(self) -> bool:
        """Start the component."""
        ...

    async def pause(self) -> bool:
        """Pause the component."""
        ...

    async def resume(self) -> bool:
        """Resume the component."""
        ...

    async def stop(self) -> bool:
        """Stop the component."""
        ...

    async def cleanup(self) -> bool:
        """Clean up component resources."""
        ...


class BaseComponentAdapter(ABC):
    """
    Base class for all component adapters.

    Provides common functionality for component lifecycle management,
    configuration, status tracking, and error handling.
    """

    def __init__(self, config: ComponentConfig):
        self.config = config
        self.status = ComponentStatus(state=ComponentState.UNINITIALIZED)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._lock = asyncio.Lock()
        self._initialized = False
        self._running = False

    @property
    def component_type(self) -> ComponentType:
        """Get the component type."""
        return self.config.component_type

    @property
    def is_enabled(self) -> bool:
        """Check if the component is enabled."""
        return self.config.enabled

    @property
    def is_ready(self) -> bool:
        """Check if the component is ready."""
        return self.status.state == ComponentState.READY

    @property
    def is_running(self) -> bool:
        """Check if the component is running."""
        return self.status.state == ComponentState.RUNNING

    @property
    def has_error(self) -> bool:
        """Check if the component has an error."""
        return self.status.state == ComponentState.ERROR

    async def initialize(self) -> bool:
        """Initialize the component."""
        if not self.is_enabled:
            self.logger.info(f"{self.component_type.value} component is disabled")
            return False

        async with self._lock:
            if self._initialized:
                return True

            try:
                self._update_status(ComponentState.INITIALIZING, "Initializing component")
                success = await self._initialize_impl()

                if success:
                    self._initialized = True
                    self._update_status(ComponentState.READY, "Component initialized successfully")
                    self.logger.info(f"{self.component_type.value} component initialized")
                else:
                    self._update_status(ComponentState.ERROR, "Failed to initialize component")
                    self.logger.error(f"Failed to initialize {self.component_type.value} component")

                return success

            except Exception as e:
                self._update_status(ComponentState.ERROR, f"Initialization error: {str(e)}")
                self.logger.exception(f"Error initializing {self.component_type.value} component")
                return False

    async def start(self) -> bool:
        """Start the component."""
        if not self.is_enabled:
            return False

        async with self._lock:
            if not self._initialized:
                if not await self.initialize():
                    return False

            if self._running:
                return True

            try:
                self._update_status(ComponentState.RUNNING, "Starting component")
                success = await self._start_impl()

                if success:
                    self._running = True
                    self.logger.info(f"{self.component_type.value} component started")
                else:
                    self._update_status(ComponentState.ERROR, "Failed to start component")
                    self.logger.error(f"Failed to start {self.component_type.value} component")

                return success

            except Exception as e:
                self._update_status(ComponentState.ERROR, f"Start error: {str(e)}")
                self.logger.exception(f"Error starting {self.component_type.value} component")
                return False

    async def stop(self) -> bool:
        """Stop the component."""
        async with self._lock:
            if not self._running:
                return True

            try:
                success = await self._stop_impl()

                if success:
                    self._running = False
                    self._update_status(ComponentState.STOPPED, "Component stopped")
                    self.logger.info(f"{self.component_type.value} component stopped")
                else:
                    self._update_status(ComponentState.ERROR, "Failed to stop component")
                    self.logger.error(f"Failed to stop {self.component_type.value} component")

                return success

            except Exception as e:
                self._update_status(ComponentState.ERROR, f"Stop error: {str(e)}")
                self.logger.exception(f"Error stopping {self.component_type.value} component")
                return False

    async def pause(self) -> bool:
        """Pause the component."""
        if not self._running:
            return False

        try:
            success = await self._pause_impl()

            if success:
                self._update_status(ComponentState.PAUSED, "Component paused")
                self.logger.info(f"{self.component_type.value} component paused")

            return success

        except Exception as e:
            self._update_status(ComponentState.ERROR, f"Pause error: {str(e)}")
            self.logger.exception(f"Error pausing {self.component_type.value} component")
            return False

    async def resume(self) -> bool:
        """Resume the component."""
        if self.status.state != ComponentState.PAUSED:
            return False

        try:
            success = await self._resume_impl()

            if success:
                self._update_status(ComponentState.RUNNING, "Component resumed")
                self.logger.info(f"{self.component_type.value} component resumed")

            return success

        except Exception as e:
            self._update_status(ComponentState.ERROR, f"Resume error: {str(e)}")
            self.logger.exception(f"Error resuming {self.component_type.value} component")
            return False

    async def cleanup(self) -> bool:
        """Clean up component resources."""
        try:
            success = await self._cleanup_impl()

            if success:
                self._initialized = False
                self._running = False
                self._update_status(ComponentState.UNINITIALIZED, "Component cleaned up")
                self.logger.info(f"{self.component_type.value} component cleaned up")

            return success

        except Exception as e:
            self.logger.exception(f"Error cleaning up {self.component_type.value} component")
            return False

    def get_status(self) -> ComponentStatus:
        """Get the current component status."""
        return self.status

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update component configuration."""
        self.config.config.update(new_config)
        self.logger.info(f"Updated configuration for {self.component_type.value} component")

    def _update_status(
        self, state: ComponentState, message: str = "", error: Optional[str] = None
    ) -> None:
        """Update the component status."""
        import datetime

        self.status.state = state
        self.status.message = message
        self.status.last_updated = datetime.datetime.utcnow().isoformat()

        if error:
            self.status.error = error

    # Abstract methods that must be implemented by subclasses

    @abstractmethod
    async def _initialize_impl(self) -> bool:
        """Implementation-specific initialization logic."""
        pass

    @abstractmethod
    async def _start_impl(self) -> bool:
        """Implementation-specific start logic."""
        pass

    @abstractmethod
    async def _stop_impl(self) -> bool:
        """Implementation-specific stop logic."""
        pass

    async def _pause_impl(self) -> bool:
        """Implementation-specific pause logic. Override if supported."""
        return False

    async def _resume_impl(self) -> bool:
        """Implementation-specific resume logic. Override if supported."""
        return False

    async def _cleanup_impl(self) -> bool:
        """Implementation-specific cleanup logic. Override if needed."""
        return True

    # Abstract methods for component-specific operations

    @abstractmethod
    async def execute(self, operation: str, data: Any = None, **kwargs) -> ComponentResult:
        """Execute a component-specific operation."""
        pass

    @abstractmethod
    async def get_metrics(self) -> Dict[str, Any]:
        """Get component-specific metrics."""
        pass


class ComponentManager:
    """
    Manages multiple component adapters and their interactions.

    Provides centralized lifecycle management, configuration, and monitoring
    for all components in the EVOSEAL system.
    """

    def __init__(self):
        self.components: Dict[ComponentType, BaseComponentAdapter] = {}
        self.logger = logging.getLogger(f"{__name__}.ComponentManager")

    def register_component(self, adapter: BaseComponentAdapter) -> None:
        """Register a component adapter."""
        self.components[adapter.component_type] = adapter
        self.logger.info(f"Registered {adapter.component_type.value} component")

    def get_component(self, component_type: ComponentType) -> Optional[BaseComponentAdapter]:
        """Get a component adapter by type."""
        return self.components.get(component_type)

    async def initialize_all(self) -> Dict[ComponentType, bool]:
        """Initialize all registered components."""
        results = {}

        for component_type, adapter in self.components.items():
            try:
                results[component_type] = await adapter.initialize()
            except Exception as e:
                self.logger.exception(f"Error initializing {component_type.value} component")
                results[component_type] = False

        return results

    async def start_all(self) -> Dict[ComponentType, bool]:
        """Start all registered components."""
        results = {}

        for component_type, adapter in self.components.items():
            try:
                results[component_type] = await adapter.start()
            except Exception as e:
                self.logger.exception(f"Error starting {component_type.value} component")
                results[component_type] = False

        return results

    async def stop_all(self) -> Dict[ComponentType, bool]:
        """Stop all registered components."""
        results = {}

        for component_type, adapter in self.components.items():
            try:
                results[component_type] = await adapter.stop()
            except Exception as e:
                self.logger.exception(f"Error stopping {component_type.value} component")
                results[component_type] = False

        return results

    def get_all_status(self) -> Dict[ComponentType, ComponentStatus]:
        """Get status of all registered components."""
        return {
            component_type: adapter.get_status()
            for component_type, adapter in self.components.items()
        }

    async def get_all_metrics(self) -> Dict[ComponentType, Dict[str, Any]]:
        """Get metrics from all registered components."""
        metrics = {}

        for component_type, adapter in self.components.items():
            try:
                metrics[component_type] = await adapter.get_metrics()
            except Exception as e:
                self.logger.exception(
                    f"Error getting metrics from {component_type.value} component"
                )
                metrics[component_type] = {"error": str(e)}

        return metrics
