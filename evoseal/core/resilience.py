"""Comprehensive resilience and error handling system for EVOSEAL pipeline.

This module provides advanced error handling, recovery strategies, circuit breakers,
health monitoring, and failure isolation mechanisms to ensure pipeline resilience.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from evoseal.core.errors import (
    BaseError,
    ErrorCategory,
    ErrorSeverity,
    IntegrationError,
    RetryableError,
)
from evoseal.core.events import Event, EventBus, create_error_event

logger = logging.getLogger(__name__)
event_bus = EventBus()


class ComponentHealth(Enum):
    """Health status of pipeline components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class FailureMode(Enum):
    """Types of failure modes."""

    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPENDENCY_FAILURE = "dependency_failure"
    VALIDATION_FAILURE = "validation_failure"
    NETWORK_ERROR = "network_error"


@dataclass
class FailureRecord:
    """Record of a failure occurrence."""

    timestamp: datetime
    component: str
    operation: str
    failure_mode: FailureMode
    error: Optional[Exception] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False


@dataclass
class HealthMetrics:
    """Health metrics for a component."""

    component: str
    health_status: ComponentHealth
    success_rate: float
    error_rate: float
    avg_response_time: float
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening circuit
    recovery_timeout: int = 60  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close circuit
    timeout: float = 30.0  # Operation timeout in seconds


class CircuitBreaker:
    """Circuit breaker implementation for failure isolation."""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.next_attempt_time: Optional[datetime] = None

    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        now = datetime.utcnow()

        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if self.next_attempt_time and now >= self.next_attempt_time:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                return True
            return False
        else:  # HALF_OPEN
            return True

    def record_success(self):
        """Record a successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit breaker {self.name} closed after recovery")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.next_attempt_time = datetime.utcnow() + timedelta(
                    seconds=self.config.recovery_timeout
                )
                logger.warning(f"Circuit breaker {self.name} opened due to failures")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.next_attempt_time = datetime.utcnow() + timedelta(
                seconds=self.config.recovery_timeout
            )
            logger.warning(f"Circuit breaker {self.name} reopened after failed test")


class HealthMonitor:
    """Monitors health of pipeline components."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics: Dict[str, HealthMetrics] = {}
        self.operation_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.response_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))

    def record_operation(
        self,
        component: str,
        operation: str,
        success: bool,
        response_time: float,
        error: Optional[Exception] = None,
    ):
        """Record an operation result."""
        timestamp = datetime.utcnow()

        # Update operation history
        self.operation_history[component].append(
            {
                "timestamp": timestamp,
                "operation": operation,
                "success": success,
                "response_time": response_time,
                "error": error,
            }
        )

        self.response_times[component].append(response_time)

        # Update or create health metrics
        if component not in self.metrics:
            self.metrics[component] = HealthMetrics(
                component=component,
                health_status=ComponentHealth.UNKNOWN,
                success_rate=0.0,
                error_rate=0.0,
                avg_response_time=0.0,
            )

        metrics = self.metrics[component]

        # Update counters
        if success:
            metrics.last_success = timestamp
            metrics.consecutive_failures = 0
            metrics.consecutive_successes += 1
        else:
            metrics.last_failure = timestamp
            metrics.consecutive_successes = 0
            metrics.consecutive_failures += 1

        # Calculate rates
        history = self.operation_history[component]
        if history:
            successes = sum(1 for op in history if op["success"])
            metrics.success_rate = successes / len(history)
            metrics.error_rate = 1.0 - metrics.success_rate

        # Calculate average response time
        if self.response_times[component]:
            metrics.avg_response_time = sum(self.response_times[component]) / len(
                self.response_times[component]
            )

        # Determine health status
        metrics.health_status = self._calculate_health_status(metrics)

    def _calculate_health_status(self, metrics: HealthMetrics) -> ComponentHealth:
        """Calculate health status based on metrics."""
        if metrics.consecutive_failures >= 10:
            return ComponentHealth.CRITICAL
        elif metrics.consecutive_failures >= 5:
            return ComponentHealth.UNHEALTHY
        elif metrics.error_rate > 0.5:
            return ComponentHealth.DEGRADED
        elif metrics.success_rate > 0.9:
            return ComponentHealth.HEALTHY
        else:
            return ComponentHealth.DEGRADED

    def get_component_health(self, component: str) -> Optional[HealthMetrics]:
        """Get health metrics for a component."""
        return self.metrics.get(component)

    def get_unhealthy_components(self) -> List[str]:
        """Get list of unhealthy components."""
        return [
            component
            for component, metrics in self.metrics.items()
            if metrics.health_status in [ComponentHealth.UNHEALTHY, ComponentHealth.CRITICAL]
        ]


class ResilienceManager:
    """Comprehensive resilience manager for the EVOSEAL pipeline."""

    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.health_monitor = HealthMonitor()
        self.failure_history: List[FailureRecord] = []
        self.recovery_strategies: Dict[str, Callable] = {}
        self.degradation_handlers: Dict[str, Callable] = {}
        self.isolation_policies: Dict[str, Set[str]] = {}
        self.event_bus = event_bus
        self._monitoring_task = None
        self._monitoring_started = False
        self.max_failure_history = 1000
        self.health_check_interval = 30  # seconds
        self.auto_recovery_enabled = True

    def register_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """Register a circuit breaker for a component."""
        if config is None:
            config = CircuitBreakerConfig()
        self.circuit_breakers[name] = CircuitBreaker(name, config)
        logger.info(f"Registered circuit breaker for {name}")

    def register_recovery_strategy(self, component: str, strategy: Callable):
        """Register a recovery strategy for a component."""
        self.recovery_strategies[component] = strategy
        logger.info(f"Registered recovery strategy for {component}")

    def register_degradation_handler(self, component: str, handler: Callable):
        """Register a graceful degradation handler."""
        self.degradation_handlers[component] = handler
        logger.info(f"Registered degradation handler for {component}")

    def set_isolation_policy(self, component: str, isolated_components: Set[str]):
        """Set isolation policy - which components to isolate when this one fails."""
        self.isolation_policies[component] = isolated_components
        logger.info(f"Set isolation policy for {component}: {isolated_components}")

    async def execute_with_resilience(
        self,
        component: str,
        operation: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Execute a function with comprehensive resilience mechanisms."""
        start_time = time.time()

        # Check circuit breaker
        circuit_breaker = self.circuit_breakers.get(component)
        if circuit_breaker and not circuit_breaker.can_execute():
            error = IntegrationError(
                f"Circuit breaker open for {component}",
                system=component,
                severity=ErrorSeverity.WARNING,
            )
            await self._handle_circuit_breaker_open(component, error)
            raise error

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Record success
            response_time = time.time() - start_time
            self.health_monitor.record_operation(component, operation, True, response_time)

            if circuit_breaker:
                circuit_breaker.record_success()

            return result

        except Exception as e:
            response_time = time.time() - start_time

            # Record failure
            self.health_monitor.record_operation(component, operation, False, response_time, e)

            if circuit_breaker:
                circuit_breaker.record_failure()

            # Record failure for analysis
            failure_record = FailureRecord(
                timestamp=datetime.utcnow(),
                component=component,
                operation=operation,
                failure_mode=self._classify_failure(e),
                error=e,
                context={"args": str(args), "kwargs": str(kwargs)},
            )
            self._record_failure(failure_record)

            # Attempt recovery
            if self.auto_recovery_enabled:
                recovery_successful = await self._attempt_recovery(
                    component, operation, e, failure_record
                )
                if recovery_successful:
                    # Retry the operation once after successful recovery
                    try:
                        if asyncio.iscoroutinefunction(func):
                            result = await func(*args, **kwargs)
                        else:
                            result = func(*args, **kwargs)

                        failure_record.recovery_successful = True
                        return result
                    except Exception as retry_error:
                        logger.error(f"Retry after recovery failed: {retry_error}")

            # Handle failure isolation
            await self._handle_failure_isolation(component, e)

            # Publish error event
            await event_bus.publish(
                create_error_event(
                    error=e,
                    source="resilience_manager",
                    component=component,
                    operation=operation,
                )
            )

            raise

    def _classify_failure(self, error: Exception) -> FailureMode:
        """Classify the type of failure."""
        if isinstance(error, TimeoutError):
            return FailureMode.TIMEOUT
        elif isinstance(error, (ConnectionError, OSError)):
            return FailureMode.NETWORK_ERROR
        elif isinstance(error, MemoryError):
            return FailureMode.RESOURCE_EXHAUSTION
        elif isinstance(error, IntegrationError):
            return FailureMode.DEPENDENCY_FAILURE
        else:
            return FailureMode.EXCEPTION

    def _record_failure(self, failure_record: FailureRecord):
        """Record a failure for analysis."""
        self.failure_history.append(failure_record)

        # Limit history size
        if len(self.failure_history) > self.max_failure_history:
            self.failure_history = self.failure_history[-self.max_failure_history :]

    async def _attempt_recovery(
        self,
        component: str,
        operation: str,
        error: Exception,
        failure_record: FailureRecord,
    ) -> bool:
        """Attempt to recover from a failure."""
        failure_record.recovery_attempted = True

        # Try component-specific recovery strategy
        if component in self.recovery_strategies:
            try:
                strategy = self.recovery_strategies[component]
                if asyncio.iscoroutinefunction(strategy):
                    await strategy(component, operation, error)
                else:
                    strategy(component, operation, error)

                logger.info(f"Recovery successful for {component}")
                return True
            except Exception as recovery_error:
                logger.error(f"Recovery failed for {component}: {recovery_error}")

        # Try generic recovery based on failure type
        failure_mode = self._classify_failure(error)
        if failure_mode == FailureMode.TIMEOUT:
            # Wait and retry
            await asyncio.sleep(5)
            return True
        elif failure_mode == FailureMode.NETWORK_ERROR:
            # Wait longer for network issues
            await asyncio.sleep(10)
            return True

        return False

    async def _handle_circuit_breaker_open(self, component: str, error: Exception):
        """Handle circuit breaker being open."""
        # Try graceful degradation
        if component in self.degradation_handlers:
            try:
                handler = self.degradation_handlers[component]
                if asyncio.iscoroutinefunction(handler):
                    await handler(component, error)
                else:
                    handler(component, error)
                logger.info(f"Graceful degradation activated for {component}")
            except Exception as degradation_error:
                logger.error(f"Graceful degradation failed for {component}: {degradation_error}")

    async def _handle_failure_isolation(self, component: str, error: Exception):
        """Handle failure isolation policies."""
        if component in self.isolation_policies:
            isolated_components = self.isolation_policies[component]
            logger.warning(
                f"Isolating components due to {component} failure: {isolated_components}"
            )

            # Notify about isolation
            await event_bus.publish(
                Event(
                    event_type="COMPONENT_ISOLATED",
                    source="resilience_manager",
                    data={
                        "failed_component": component,
                        "isolated_components": list(isolated_components),
                        "error": str(error),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            )

    async def start_monitoring(self):
        """Start background health monitoring."""
        if self._monitoring_started:
            return

        async def health_check_loop():
            while self._monitoring_started:
                try:
                    await self._perform_health_checks()
                    await asyncio.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
                    await asyncio.sleep(60)  # Wait longer on error

        self._monitoring_started = True
        self._monitoring_task = asyncio.create_task(health_check_loop())

    async def stop_monitoring(self):
        """Stop background health monitoring."""
        self._monitoring_started = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

    async def _perform_health_checks(self):
        """Perform health checks on all components."""
        unhealthy_components = self.health_monitor.get_unhealthy_components()

        for component in unhealthy_components:
            metrics = self.health_monitor.get_component_health(component)
            if metrics:
                logger.warning(
                    f"Component {component} is {metrics.health_status.value}: "
                    f"success_rate={metrics.success_rate:.2f}, "
                    f"consecutive_failures={metrics.consecutive_failures}"
                )

                # Publish health event
                await event_bus.publish(
                    Event(
                        event_type="COMPONENT_HEALTH_DEGRADED",
                        source="resilience_manager",
                        data={
                            "component": component,
                            "health_status": metrics.health_status.value,
                            "success_rate": metrics.success_rate,
                            "error_rate": metrics.error_rate,
                            "consecutive_failures": metrics.consecutive_failures,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                )

    def get_resilience_status(self) -> Dict[str, Any]:
        """Get comprehensive resilience status."""
        return {
            "circuit_breakers": {
                name: {
                    "state": cb.state.value,
                    "failure_count": cb.failure_count,
                    "last_failure": (
                        cb.last_failure_time.isoformat() if cb.last_failure_time else None
                    ),
                }
                for name, cb in self.circuit_breakers.items()
            },
            "component_health": {
                component: {
                    "status": metrics.health_status.value,
                    "success_rate": metrics.success_rate,
                    "error_rate": metrics.error_rate,
                    "consecutive_failures": metrics.consecutive_failures,
                    "avg_response_time": metrics.avg_response_time,
                }
                for component, metrics in self.health_monitor.metrics.items()
            },
            "recent_failures": [
                {
                    "timestamp": record.timestamp.isoformat(),
                    "component": record.component,
                    "operation": record.operation,
                    "failure_mode": record.failure_mode.value,
                    "recovery_attempted": record.recovery_attempted,
                    "recovery_successful": record.recovery_successful,
                }
                for record in self.failure_history[-10:]  # Last 10 failures
            ],
        }


# Global resilience manager instance
resilience_manager = ResilienceManager()
