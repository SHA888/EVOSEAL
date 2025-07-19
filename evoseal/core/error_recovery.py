"""Comprehensive error recovery system for EVOSEAL pipeline.

This module provides advanced error recovery strategies, automatic retries,
fallback mechanisms, and intelligent error analysis for pipeline resilience.
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from evoseal.core.errors import BaseError, ErrorCategory, ErrorSeverity
from evoseal.core.events import Event, EventBus, create_error_event
from evoseal.core.logging_system import get_logger

logger = get_logger("error_recovery")
event_bus = EventBus()


class RecoveryAction(Enum):
    """Types of recovery actions."""

    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    RESTART_COMPONENT = "restart_component"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    CIRCUIT_BREAK = "circuit_break"


class RecoveryResult(Enum):
    """Results of recovery attempts."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ESCALATED = "escalated"


@dataclass
class RecoveryStrategy:
    """Configuration for error recovery strategy."""

    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay: float = 300.0
    timeout: float = 30.0
    fallback_enabled: bool = True
    escalation_threshold: int = 5
    recovery_actions: List[RecoveryAction] = field(
        default_factory=lambda: [RecoveryAction.RETRY, RecoveryAction.FALLBACK]
    )


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""

    timestamp: datetime
    component: str
    operation: str
    error: Exception
    action: RecoveryAction
    result: RecoveryResult
    duration: float
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0


@dataclass
class ErrorPattern:
    """Pattern for error classification and recovery."""

    error_type: str
    error_message_pattern: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    recovery_strategy: Optional[RecoveryStrategy] = None
    custom_handler: Optional[Callable] = None


class ErrorClassifier:
    """Classifies errors and determines appropriate recovery strategies."""

    def __init__(self):
        self.patterns: List[ErrorPattern] = []
        self.error_history: Dict[str, List[Exception]] = defaultdict(list)
        self.recovery_success_rates: Dict[str, Dict[RecoveryAction, float]] = defaultdict(dict)

    def register_pattern(self, pattern: ErrorPattern):
        """Register an error pattern for classification."""
        self.patterns.append(pattern)
        logger.info(f"Registered error pattern for {pattern.error_type}")

    def classify_error(
        self, error: Exception, component: str, operation: str
    ) -> Optional[ErrorPattern]:
        """Classify an error and return matching pattern."""
        error_type = error.__class__.__name__
        error_message = str(error)

        # Record error in history
        key = f"{component}:{operation}"
        self.error_history[key].append(error)

        # Find matching pattern
        for pattern in self.patterns:
            if pattern.error_type == error_type:
                if pattern.component and pattern.component != component:
                    continue
                if pattern.operation and pattern.operation != operation:
                    continue
                if (
                    pattern.error_message_pattern
                    and pattern.error_message_pattern not in error_message
                ):
                    continue
                return pattern

        return None

    def get_error_frequency(self, component: str, operation: str) -> int:
        """Get frequency of errors for a component/operation."""
        key = f"{component}:{operation}"
        return len(self.error_history[key])

    def update_recovery_success_rate(self, component: str, action: RecoveryAction, success: bool):
        """Update success rate for a recovery action."""
        if component not in self.recovery_success_rates:
            self.recovery_success_rates[component] = {}

        if action not in self.recovery_success_rates[component]:
            self.recovery_success_rates[component][action] = 0.5  # Start with neutral

        # Simple moving average update
        current_rate = self.recovery_success_rates[component][action]
        new_rate = current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
        self.recovery_success_rates[component][action] = new_rate

    def get_best_recovery_action(
        self, component: str, available_actions: List[RecoveryAction]
    ) -> RecoveryAction:
        """Get the recovery action with highest success rate."""
        if component not in self.recovery_success_rates:
            return available_actions[0] if available_actions else RecoveryAction.RETRY

        rates = self.recovery_success_rates[component]
        best_action = None
        best_rate = -1

        for action in available_actions:
            if action in rates and rates[action] > best_rate:
                best_action = action
                best_rate = rates[action]

        return best_action or available_actions[0]


class FallbackManager:
    """Manages fallback mechanisms for failed operations."""

    def __init__(self):
        self.fallback_handlers: Dict[str, Callable] = {}
        self.fallback_data: Dict[str, Any] = {}

    def register_fallback(
        self, component: str, operation: str, handler: Callable, fallback_data: Optional[Any] = None
    ):
        """Register a fallback handler for a component operation."""
        key = f"{component}:{operation}"
        self.fallback_handlers[key] = handler
        if fallback_data is not None:
            self.fallback_data[key] = fallback_data
        logger.info(f"Registered fallback for {key}")

    async def execute_fallback(
        self, component: str, operation: str, original_error: Exception, *args, **kwargs
    ) -> Any:
        """Execute fallback for a failed operation."""
        key = f"{component}:{operation}"

        if key not in self.fallback_handlers:
            raise ValueError(f"No fallback registered for {key}")

        handler = self.fallback_handlers[key]
        fallback_data = self.fallback_data.get(key)

        try:
            logger.info(f"Executing fallback for {key}")

            # Prepare fallback context
            context = {
                "original_error": original_error,
                "component": component,
                "operation": operation,
                "fallback_data": fallback_data,
            }

            # Execute fallback
            if asyncio.iscoroutinefunction(handler):
                result = await handler(*args, context=context, **kwargs)
            else:
                result = handler(*args, context=context, **kwargs)

            logger.info(f"Fallback successful for {key}")
            return result

        except Exception as fallback_error:
            logger.error(f"Fallback failed for {key}: {fallback_error}")
            raise


class ErrorRecoveryManager:
    """Comprehensive error recovery manager."""

    def __init__(self):
        self.classifier = ErrorClassifier()
        self.fallback_manager = FallbackManager()
        self.recovery_attempts: List[RecoveryAttempt] = []
        self.component_states: Dict[str, str] = {}
        self.escalation_handlers: Dict[str, Callable] = {}

        # Default recovery strategies
        self.default_strategies = {
            ErrorCategory.NETWORK: RecoveryStrategy(
                max_retries=5,
                retry_delay=2.0,
                backoff_multiplier=1.5,
                recovery_actions=[RecoveryAction.RETRY, RecoveryAction.FALLBACK],
            ),
            ErrorCategory.TIMEOUT: RecoveryStrategy(
                max_retries=3,
                retry_delay=5.0,
                recovery_actions=[RecoveryAction.RETRY, RecoveryAction.RESTART_COMPONENT],
            ),
            ErrorCategory.RESOURCE: RecoveryStrategy(
                max_retries=2,
                retry_delay=10.0,
                recovery_actions=[RecoveryAction.GRACEFUL_DEGRADATION, RecoveryAction.RETRY],
            ),
            ErrorCategory.INTEGRATION: RecoveryStrategy(
                max_retries=3,
                retry_delay=3.0,
                recovery_actions=[
                    RecoveryAction.RETRY,
                    RecoveryAction.FALLBACK,
                    RecoveryAction.CIRCUIT_BREAK,
                ],
            ),
        }

        self._register_default_patterns()

    def _register_default_patterns(self):
        """Register default error patterns."""
        # Timeout errors
        self.classifier.register_pattern(
            ErrorPattern(
                error_type="TimeoutError",
                recovery_strategy=self.default_strategies[ErrorCategory.TIMEOUT],
            )
        )

        # Connection errors
        self.classifier.register_pattern(
            ErrorPattern(
                error_type="ConnectionError",
                recovery_strategy=self.default_strategies[ErrorCategory.NETWORK],
            )
        )

        # Memory errors
        self.classifier.register_pattern(
            ErrorPattern(
                error_type="MemoryError",
                recovery_strategy=self.default_strategies[ErrorCategory.RESOURCE],
            )
        )

    def register_escalation_handler(self, component: str, handler: Callable):
        """Register an escalation handler for a component."""
        self.escalation_handlers[component] = handler
        logger.info(f"Registered escalation handler for {component}")

    async def recover_from_error(
        self,
        error: Exception,
        component: str,
        operation: str,
        original_func: Callable,
        *args,
        **kwargs,
    ) -> Tuple[Any, RecoveryResult]:
        """Attempt to recover from an error."""
        recovery_start = time.time()

        # Classify the error
        pattern = self.classifier.classify_error(error, component, operation)
        strategy = pattern.recovery_strategy if pattern else self._get_default_strategy(error)

        logger.info(
            f"Starting recovery for {component}:{operation} - {error.__class__.__name__}",
            error_type=error.__class__.__name__,
            component=component,
            operation=operation,
        )

        # Try recovery actions in order
        for action in strategy.recovery_actions:
            try:
                result = await self._execute_recovery_action(
                    action, error, component, operation, original_func, strategy, *args, **kwargs
                )

                # Record successful recovery
                attempt = RecoveryAttempt(
                    timestamp=datetime.utcnow(),
                    component=component,
                    operation=operation,
                    error=error,
                    action=action,
                    result=RecoveryResult.SUCCESS,
                    duration=time.time() - recovery_start,
                )
                self.recovery_attempts.append(attempt)

                # Update success rates
                self.classifier.update_recovery_success_rate(component, action, True)

                logger.info(
                    f"Recovery successful for {component}:{operation} using {action.value}",
                    recovery_action=action.value,
                    duration=attempt.duration,
                )

                # Publish recovery event
                await event_bus.publish(
                    Event(
                        event_type="ERROR_RECOVERY_SUCCESS",
                        source="error_recovery",
                        data={
                            "component": component,
                            "operation": operation,
                            "error_type": error.__class__.__name__,
                            "recovery_action": action.value,
                            "duration": attempt.duration,
                        },
                    )
                )

                return result, RecoveryResult.SUCCESS

            except Exception as recovery_error:
                logger.warning(
                    f"Recovery action {action.value} failed for {component}:{operation}: {recovery_error}",
                    recovery_action=action.value,
                    recovery_error=str(recovery_error),
                )

                # Update failure rates
                self.classifier.update_recovery_success_rate(component, action, False)

                # Record failed attempt
                attempt = RecoveryAttempt(
                    timestamp=datetime.utcnow(),
                    component=component,
                    operation=operation,
                    error=error,
                    action=action,
                    result=RecoveryResult.FAILED,
                    duration=time.time() - recovery_start,
                    context={"recovery_error": str(recovery_error)},
                )
                self.recovery_attempts.append(attempt)

                continue

        # All recovery actions failed - try escalation
        if await self._should_escalate(component, operation):
            try:
                result = await self._escalate_error(error, component, operation, *args, **kwargs)
                return result, RecoveryResult.ESCALATED
            except Exception as escalation_error:
                logger.error(f"Escalation failed: {escalation_error}")

        # Complete failure
        logger.error(f"All recovery attempts failed for {component}:{operation}")

        # Publish recovery failure event
        await event_bus.publish(
            Event(
                event_type="ERROR_RECOVERY_FAILED",
                source="error_recovery",
                data={
                    "component": component,
                    "operation": operation,
                    "error_type": error.__class__.__name__,
                    "attempts": len(strategy.recovery_actions),
                },
            )
        )

        return None, RecoveryResult.FAILED

    async def _execute_recovery_action(
        self,
        action: RecoveryAction,
        error: Exception,
        component: str,
        operation: str,
        original_func: Callable,
        strategy: RecoveryStrategy,
        *args,
        **kwargs,
    ) -> Any:
        """Execute a specific recovery action."""
        if action == RecoveryAction.RETRY:
            return await self._retry_with_backoff(original_func, strategy, *args, **kwargs)
        elif action == RecoveryAction.FALLBACK:
            return await self.fallback_manager.execute_fallback(
                component, operation, error, *args, **kwargs
            )
        elif action == RecoveryAction.RESTART_COMPONENT:
            await self._restart_component(component)
            return await original_func(*args, **kwargs)
        elif action == RecoveryAction.GRACEFUL_DEGRADATION:
            return await self._graceful_degradation(component, operation, error)
        elif action == RecoveryAction.SKIP:
            logger.warning(f"Skipping operation {component}:{operation} due to error")
            return None
        else:
            raise ValueError(f"Unsupported recovery action: {action}")

    async def _retry_with_backoff(
        self, func: Callable, strategy: RecoveryStrategy, *args, **kwargs
    ) -> Any:
        """Retry function with exponential backoff."""
        delay = strategy.retry_delay

        for attempt in range(strategy.max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=strategy.timeout)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                if attempt == strategy.max_retries - 1:
                    raise

                logger.info(
                    f"Retry attempt {attempt + 1}/{strategy.max_retries} failed, waiting {delay}s"
                )
                await asyncio.sleep(delay)
                delay = min(delay * strategy.backoff_multiplier, strategy.max_delay)

    async def _restart_component(self, component: str):
        """Restart a component."""
        logger.info(f"Restarting component {component}")

        # Set component state
        self.component_states[component] = "restarting"

        # Simulate restart delay
        await asyncio.sleep(2)

        # Update state
        self.component_states[component] = "running"

        logger.info(f"Component {component} restarted successfully")

    async def _graceful_degradation(self, component: str, operation: str, error: Exception) -> Any:
        """Implement graceful degradation."""
        logger.info(f"Implementing graceful degradation for {component}:{operation}")

        # Return a safe default or cached result
        degraded_result = {
            "status": "degraded",
            "component": component,
            "operation": operation,
            "error": str(error),
            "message": "Operating in degraded mode due to error",
        }

        return degraded_result

    async def _should_escalate(self, component: str, operation: str) -> bool:
        """Determine if error should be escalated."""
        error_frequency = self.classifier.get_error_frequency(component, operation)
        return error_frequency >= 5  # Escalate after 5 errors

    async def _escalate_error(
        self, error: Exception, component: str, operation: str, *args, **kwargs
    ) -> Any:
        """Escalate error to higher-level handler."""
        if component in self.escalation_handlers:
            handler = self.escalation_handlers[component]
            logger.info(f"Escalating error for {component} to custom handler")

            if asyncio.iscoroutinefunction(handler):
                return await handler(error, component, operation, *args, **kwargs)
            else:
                return handler(error, component, operation, *args, **kwargs)
        else:
            # Default escalation - log and re-raise
            logger.critical(f"Escalating unhandled error for {component}:{operation}: {error}")
            raise error

    def _get_default_strategy(self, error: Exception) -> RecoveryStrategy:
        """Get default recovery strategy based on error type."""
        if isinstance(error, TimeoutError):
            return self.default_strategies[ErrorCategory.TIMEOUT]
        elif isinstance(error, (ConnectionError, OSError)):
            return self.default_strategies[ErrorCategory.NETWORK]
        elif isinstance(error, MemoryError):
            return self.default_strategies[ErrorCategory.RESOURCE]
        else:
            return RecoveryStrategy()  # Default strategy

    def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        if not self.recovery_attempts:
            return {}

        stats = {
            "total_attempts": len(self.recovery_attempts),
            "success_rate": 0.0,
            "by_action": defaultdict(int),
            "by_component": defaultdict(int),
            "by_result": defaultdict(int),
            "avg_duration": 0.0,
        }

        successful_attempts = 0
        total_duration = 0.0

        for attempt in self.recovery_attempts:
            if attempt.result == RecoveryResult.SUCCESS:
                successful_attempts += 1

            stats["by_action"][attempt.action.value] += 1
            stats["by_component"][attempt.component] += 1
            stats["by_result"][attempt.result.value] += 1
            total_duration += attempt.duration

        stats["success_rate"] = successful_attempts / len(self.recovery_attempts)
        stats["avg_duration"] = total_duration / len(self.recovery_attempts)

        return dict(stats)

    def clear_history(self, older_than_hours: int = 24):
        """Clear old recovery attempts."""
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        self.recovery_attempts = [
            attempt for attempt in self.recovery_attempts if attempt.timestamp > cutoff
        ]


# Global error recovery manager instance
error_recovery_manager = ErrorRecoveryManager()


def with_error_recovery(
    component: str,
    operation: str,
    recovery_strategy: Optional[RecoveryStrategy] = None,
):
    """Decorator to add error recovery to functions."""

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                result, recovery_result = await error_recovery_manager.recover_from_error(
                    e, component, operation, func, *args, **kwargs
                )
                if recovery_result == RecoveryResult.SUCCESS:
                    return result
                else:
                    raise

        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # For sync functions, we need to run recovery in async context
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                result, recovery_result = loop.run_until_complete(
                    error_recovery_manager.recover_from_error(
                        e, component, operation, func, *args, **kwargs
                    )
                )
                if recovery_result == RecoveryResult.SUCCESS:
                    return result
                else:
                    raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
