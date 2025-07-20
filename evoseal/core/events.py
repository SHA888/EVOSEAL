"""
Event system for the EVOSEAL workflow engine.

This module provides a flexible event system supporting both synchronous and
asynchronous event handling, with features like event filtering, propagation
control, and error handling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Collection, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Optional, TypeVar, Union, cast, overload

from typing_extensions import TypeAlias, TypedDict

logger = logging.getLogger(__name__)

# Type variables for better type hints
T = TypeVar("T")


class EventType(Enum):
    """Types of events in the workflow system."""

    # Workflow events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_CANCELLED = "workflow_cancelled"

    # Step events
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    STEP_RETRYING = "step_retrying"

    # Evolution pipeline events
    EVOLUTION_STARTED = "evolution_started"
    EVOLUTION_COMPLETED = "evolution_completed"
    EVOLUTION_FAILED = "evolution_failed"
    EVOLUTION_ITERATION_STARTED = "evolution_iteration_started"
    EVOLUTION_ITERATION_COMPLETED = "evolution_iteration_completed"
    EVOLUTION_ITERATION_FAILED = "evolution_iteration_failed"

    # Component events
    COMPONENT_INITIALIZED = "component_initialized"
    COMPONENT_STARTED = "component_started"
    COMPONENT_STOPPED = "component_stopped"
    COMPONENT_FAILED = "component_failed"
    COMPONENT_OPERATION_STARTED = "component_operation_started"
    COMPONENT_OPERATION_COMPLETED = "component_operation_completed"
    COMPONENT_OPERATION_FAILED = "component_operation_failed"

    # Metrics and monitoring events
    METRICS_COLLECTED = "metrics_collected"
    PERFORMANCE_THRESHOLD_EXCEEDED = "performance_threshold_exceeded"
    RESOURCE_USAGE_HIGH = "resource_usage_high"
    HEALTH_CHECK_PASSED = "health_check_passed"
    HEALTH_CHECK_FAILED = "health_check_failed"

    # Error and debugging events
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"
    DEBUG_INFO = "debug_info"
    EXCEPTION_CAUGHT = "exception_caught"

    # Pipeline stage events
    STAGE_ANALYZING = "stage_analyzing"
    STAGE_GENERATING = "stage_generating"
    STAGE_ADAPTING = "stage_adapting"
    STAGE_EVALUATING = "stage_evaluating"
    STAGE_VALIDATING = "stage_validating"
    STAGE_FINALIZING = "stage_finalizing"

    # Configuration and state events
    CONFIG_UPDATED = "config_updated"
    STATE_CHANGED = "state_changed"
    CHECKPOINT_CREATED = "checkpoint_created"

    # Rollback events
    ROLLBACK_INITIATED = "rollback_initiated"
    ROLLBACK_COMPLETED = "rollback_completed"
    ROLLBACK_FAILED = "rollback_failed"
    ROLLBACK_VERIFICATION_PASSED = "rollback_verification_passed"
    ROLLBACK_VERIFICATION_FAILED = "rollback_verification_failed"
    CASCADING_ROLLBACK_STARTED = "cascading_rollback_started"
    CASCADING_ROLLBACK_COMPLETED = "cascading_rollback_completed"

    # Regression detection events
    BASELINE_ESTABLISHED = "baseline_established"
    REGRESSION_DETECTED = "regression_detected"
    REGRESSION_ALERT = "regression_alert"

    PROGRESS_UPDATE = "progress_update"

    # Additional component events
    COMPONENT_INITIALIZING = "component_initializing"
    COMPONENT_READY = "component_ready"
    COMPONENT_PAUSED = "component_paused"
    COMPONENT_RESUMED = "component_resumed"
    COMPONENT_STATUS_CHANGED = "component_status_changed"
    COMPONENT_STARTING = "component_starting"
    COMPONENT_STOPPING = "component_stopping"

    # Additional evolution events
    ITERATION_STARTED = "iteration_started"
    ITERATION_COMPLETED = "iteration_completed"
    ITERATION_FAILED = "iteration_failed"

    # Pipeline stage events (more specific)
    PIPELINE_STAGE_STARTED = "pipeline_stage_started"
    PIPELINE_STAGE_COMPLETED = "pipeline_stage_completed"
    PIPELINE_STAGE_FAILED = "pipeline_stage_failed"

    # Additional info events
    INFO_MESSAGE = "info_message"

    # Custom events
    CUSTOM = "custom"


@dataclass
class Event:
    """Base class for all workflow events."""

    event_type: EventType | str
    source: str
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    context: dict[str, Any] = field(default_factory=dict)
    _stop_propagation: bool = field(default=False, init=False)

    def stop_propagation(self) -> None:
        """Stop further processing of this event."""
        self._stop_propagation = True

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": (
                self.event_type.value
                if isinstance(self.event_type, EventType)
                else str(self.event_type)
            ),
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create event from dictionary."""
        event_type = data["event_type"]
        # Try to convert string to EventType enum
        try:
            event_type = EventType(event_type)
        except ValueError:
            # Keep as string if not a known EventType
            pass

        return cls(
            event_type=event_type,
            source=data["source"],
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time.time()),
            context=data.get("context", {}),
        )


# Define the handler type after Event is defined
EventHandler: TypeAlias = Union[
    Callable[[Event], None],
    Callable[[Event], Awaitable[None]],
    Callable[[Event], Coroutine[Any, Any, None]],
    Callable[[Event], Optional[Awaitable[None]]],
]


# Specialized Event Classes


@dataclass
class ComponentEvent(Event):
    """Event related to component operations."""

    component_type: str = field(default="")
    component_id: str = field(default="")
    operation: str = field(default="")

    def __post_init__(self):
        """Ensure component info is in data for backward compatibility."""
        if self.component_type:
            self.data["component_type"] = self.component_type
        if self.component_id:
            self.data["component_id"] = self.component_id
        if self.operation:
            self.data["operation"] = self.operation


@dataclass
class MetricsEvent(Event):
    """Event for metrics collection and monitoring."""

    metrics: dict[str, Any] = field(default_factory=dict)
    threshold_exceeded: bool = field(default=False)
    severity: str = field(default="info")  # info, warning, error, critical

    def __post_init__(self):
        """Ensure metrics info is in data."""
        self.data["metrics"] = self.metrics
        self.data["threshold_exceeded"] = self.threshold_exceeded
        self.data["severity"] = self.severity


@dataclass
class ErrorEvent(Event):
    """Event for error reporting and handling."""

    error_type: str = field(default="")
    error_message: str = field(default="")
    stack_trace: str = field(default="")
    severity: str = field(default="error")  # warning, error, critical
    recoverable: bool = field(default=True)

    def __post_init__(self):
        """Ensure error info is in data."""
        self.data.update(
            {
                "error_type": self.error_type,
                "error_message": self.error_message,
                "stack_trace": self.stack_trace,
                "severity": self.severity,
                "recoverable": self.recoverable,
            }
        )


@dataclass
class ProgressEvent(Event):
    """Event for progress tracking and reporting."""

    current: int = field(default=0)
    total: int = field(default=0)
    percentage: float = field(default=0.0)
    stage: str = field(default="")
    message: str = field(default="")

    def __post_init__(self):
        """Calculate percentage and ensure progress info is in data."""
        if self.total > 0:
            self.percentage = (self.current / self.total) * 100

        self.data.update(
            {
                "current": self.current,
                "total": self.total,
                "percentage": self.percentage,
                "stage": self.stage,
                "message": self.message,
            }
        )


@dataclass
class StateChangeEvent(Event):
    """Event for state changes in the system."""

    old_state: str = field(default="")
    new_state: str = field(default="")
    entity_type: str = field(default="")  # pipeline, component, workflow, etc.
    entity_id: str = field(default="")

    def __post_init__(self):
        """Ensure state change info is in data."""
        self.data.update(
            {
                "old_state": self.old_state,
                "new_state": self.new_state,
                "entity_type": self.entity_type,
                "entity_id": self.entity_id,
            }
        )


class EventBus:
    """
    A flexible event bus supporting both sync and async event handling.

    Features:
    - Support for both sync and async handlers
    - Event filtering
    - Event propagation control
    - Error handling
    - Handler priorities
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        # Use str as the key type for _handlers since we'll convert EventType to str
        self._handlers: dict[str, list[dict[str, Any]]] = {}
        self._default_handlers: list[dict[str, Any]] = []

    def _add_handler_info(
        self,
        event_str: str | None,
        handler_func: EventHandler,
        priority: int,
        filter_fn: Callable[[Event], bool] | None,
    ) -> Callable[[], None]:
        """Add handler information to the appropriate handler list.

        Args:
            event_str: The event type as string, or None for all events
            handler_func: The handler function to add
            priority: Handler priority
            filter_fn: Optional filter function

        Returns:
            An unsubscribe function for this handler
        """
        handler_info: dict[str, Any] = {
            "handler": handler_func,
            "priority": priority,
            "filter_fn": filter_fn,
        }

        if event_str is None:
            self._default_handlers.append(handler_info)
        else:
            if event_str not in self._handlers:
                self._handlers[event_str] = []
            self._handlers[event_str].append(handler_info)

        def unsubscribe() -> None:
            """Unsubscribe this handler."""
            if event_str is None:
                if handler_info in self._default_handlers:
                    self._default_handlers.remove(handler_info)
            elif event_str in self._handlers and handler_info in self._handlers[event_str]:
                self._handlers[event_str].remove(handler_info)

        return unsubscribe

    def _subscribe_decorator(
        self,
        event_type: EventType | str | None,
        priority: int = 0,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> Callable[[EventHandler], EventHandler]:
        """Create a decorator for subscribing to events.

        Args:
            event_type: The type of event to subscribe to, or None for all events
            priority: Higher priority handlers are called first (default: 0)
            filter_fn: Optional function to filter which events are handled

        Returns:
            A decorator function that will register the handler
        """
        event_str = (
            event_type.value
            if isinstance(event_type, EventType)
            else str(event_type) if event_type is not None else None
        )

        def decorator(handler_func: EventHandler) -> EventHandler:
            self._add_handler_info(event_str, handler_func, priority, filter_fn)
            return handler_func

        return decorator

    def _subscribe_direct(
        self,
        event_type: EventType | str | None,
        handler: EventHandler,
        priority: int = 0,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> Callable[[], None]:
        """Subscribe a handler function directly.

        Args:
            event_type: The type of event to subscribe to, or None for all events
            handler: The callback function to handle the event
            priority: Higher priority handlers are called first (default: 0)
            filter_fn: Optional function to filter which events are handled

        Returns:
            An unsubscribe function for this handler
        """
        event_str = event_type.value if isinstance(event_type, EventType) else event_type
        return self._add_handler_info(event_str, handler, priority, filter_fn)

    @overload
    def subscribe(
        self,
        event_type: EventType | str | None = None,
        *,
        priority: int = 0,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> Callable[[EventHandler], EventHandler]: ...

    @overload
    def subscribe(
        self,
        event_type: EventHandler,
    ) -> EventHandler: ...

    @overload
    def subscribe(
        self,
        event_type: EventType | str | None,
        handler: EventHandler,
        *,
        priority: int = 0,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> Callable[[], None]: ...

    def subscribe(
        self,
        event_type: EventType | str | Callable[[Event], None | Awaitable[None]] | None = None,
        handler: EventHandler | None = None,
        *,
        priority: int = 0,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> Callable[[], None] | Callable[[EventHandler], EventHandler] | EventHandler:
        """
        Subscribe to events of a specific type.

        This method supports three usage patterns:
        1. Direct call with handler: subscribe(event_type, handler, ...)
        2. Decorator with arguments: @subscribe(event_type, priority=...)
        3. Simple decorator: @subscribe

        Args:
            event_type: The type of event to subscribe to, or None for all events.
                       Can also be the handler when used as a simple decorator.
            handler: The callback function to handle the event
            priority: Higher priority handlers are called first (default: 0)
            filter_fn: Optional function to filter which events are handled

        Returns:
            - For direct calls: An unsubscribe function
            - For decorators: A decorator function
        """
        # Handle @subscribe (no arguments) case
        if event_type is not None and callable(event_type):
            return self._subscribe_decorator(None, 0, None)(event_type)

        # Handle @subscribe() with arguments case
        if handler is None:
            return self._subscribe_decorator(event_type, priority, filter_fn)

        # Handle direct call case: subscribe(event_type, handler, ...)
        return self._subscribe_direct(event_type, handler, priority, filter_fn)

    def unsubscribe(
        self,
        event_type: EventType | str | None,
        handler: EventHandler,
    ) -> None:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: The event type to unsubscribe from, or None for all events
            handler: The handler function to remove
        """
        if event_type is None:
            self._default_handlers = [h for h in self._default_handlers if h["handler"] != handler]
        else:
            event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
            if event_type_str in self._handlers:
                self._handlers[event_type_str] = [
                    h for h in self._handlers[event_type_str] if h["handler"] != handler
                ]

    async def publish(self, event: Event | str, **kwargs: Any) -> Event:
        """
        Publish an event to all subscribers.

        Args:
            event: Event instance or event type string
            **kwargs: Additional data for the event

        Returns:
            The event object after processing
        """
        # Create event object if a string is provided
        if isinstance(event, str):
            event = Event(event_type=event, source="system", data=kwargs)
        elif kwargs:
            # Update event data with any additional kwargs
            event.data.update(kwargs)

        # Get event type as string for handler lookup
        event_type = (
            event.event_type.value
            if isinstance(event.event_type, EventType)
            else str(event.event_type)
        )

        # Get all relevant handlers
        handlers = self._default_handlers.copy()
        if event_type in self._handlers:
            handlers.extend(self._handlers[event_type])

        # Sort by priority (highest first)
        handlers.sort(key=lambda x: cast(int, x["priority"]), reverse=True)

        # Process handlers
        for handler_info in handlers:
            if event._stop_propagation:
                break

            # Skip if filter doesn't pass
            if handler_info.get("filter_fn") and not handler_info["filter_fn"](event):
                continue

            try:
                handler = handler_info["handler"]
                if asyncio.iscoroutinefunction(handler) or asyncio.iscoroutine(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    f"Error in {handler_info['handler'].__name__} "
                    f"for event {event.event_type}: {str(e)}",
                    exc_info=True,
                )

        return event

    def get_event_history(
        self, event_type: EventType | str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get recent event history.

        Args:
            event_type: Filter by event type, or None for all events
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries sorted by timestamp (newest first)
        """
        if not hasattr(self, '_event_history'):
            return []

        events = self._event_history

        # Filter by event type if specified
        if event_type is not None:
            event_type_str = (
                event_type.value if isinstance(event_type, EventType) else str(event_type)
            )
            events = [e for e in events if e.get('event_type') == event_type_str]

        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        return events[:limit]

    def clear_event_history(self) -> None:
        """Clear the event history."""
        if hasattr(self, '_event_history'):
            self._event_history.clear()

    def enable_event_logging(self, max_history: int = 1000) -> None:
        """Enable event logging and history tracking.

        Args:
            max_history: Maximum number of events to keep in history
        """
        self._event_history: list[dict[str, Any]] = []
        self._max_history = max_history
        self._logging_enabled = True

        # Subscribe to all events for logging
        @self.subscribe(priority=1000)  # High priority to log before other handlers
        async def log_event(event: Event) -> None:
            """Log all events for history tracking."""
            if hasattr(self, '_event_history'):
                event_dict = event.to_dict()
                self._event_history.append(event_dict)

                # Trim history if it exceeds max size
                if len(self._event_history) > self._max_history:
                    self._event_history = self._event_history[-self._max_history :]

                # Log to standard logger based on event type
                event_type_str = event_dict['event_type']
                if 'error' in event_type_str.lower() or 'failed' in event_type_str.lower():
                    logger.error(f"Event: {event_type_str} from {event.source}: {event.data}")
                elif 'warning' in event_type_str.lower():
                    logger.warning(f"Event: {event_type_str} from {event.source}: {event.data}")
                else:
                    logger.info(f"Event: {event_type_str} from {event.source}")

    def disable_event_logging(self) -> None:
        """Disable event logging."""
        self._logging_enabled = False
        if hasattr(self, '_event_history'):
            del self._event_history

    def get_handler_count(self, event_type: EventType | str | None = None) -> int:
        """Get the number of handlers for an event type.

        Args:
            event_type: Event type to check, or None for default handlers

        Returns:
            Number of handlers registered for the event type
        """
        if event_type is None:
            return len(self._default_handlers)

        event_type_str = event_type.value if isinstance(event_type, EventType) else str(event_type)
        return len(self._handlers.get(event_type_str, []))

    def get_all_event_types(self) -> list[str]:
        """Get all event types that have registered handlers.

        Returns:
            List of event type strings
        """
        return list(self._handlers.keys())

    async def publish_batch(self, events: list[Event | str], **common_kwargs: Any) -> list[Event]:
        """Publish multiple events in batch.

        Args:
            events: List of events to publish
            **common_kwargs: Common data to add to all events

        Returns:
            List of processed events
        """
        results = []
        for event in events:
            try:
                result = await self.publish(event, **common_kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Error publishing event in batch: {e}")
                # Create error event for failed publication
                if isinstance(event, str):
                    error_event = Event(
                        event_type=EventType.ERROR_OCCURRED,
                        source="event_bus",
                        data={"error": str(e), "failed_event_type": event},
                    )
                else:
                    error_event = Event(
                        event_type=EventType.ERROR_OCCURRED,
                        source="event_bus",
                        data={"error": str(e), "failed_event_type": str(event.event_type)},
                    )
                results.append(error_event)

        return results


class EnhancedEventBus(EventBus):
    """Enhanced event bus with additional monitoring and filtering capabilities."""

    def __init__(self, enable_metrics: bool = True, enable_logging: bool = True):
        """Initialize enhanced event bus.

        Args:
            enable_metrics: Whether to collect event metrics
            enable_logging: Whether to enable event logging
        """
        super().__init__()
        self._metrics_enabled = enable_metrics
        self._event_metrics: dict[str, dict[str, Any]] = {}

        if enable_logging:
            self.enable_event_logging()

        if enable_metrics:
            self._init_metrics_collection()

    def _init_metrics_collection(self) -> None:
        """Initialize metrics collection for events."""

        @self.subscribe(priority=999)  # High priority for metrics
        async def collect_metrics(event: Event) -> None:
            """Collect metrics for all events."""
            if not self._metrics_enabled:
                return

            event_type_str = (
                event.event_type.value
                if isinstance(event.event_type, EventType)
                else str(event.event_type)
            )

            if event_type_str not in self._event_metrics:
                self._event_metrics[event_type_str] = {
                    "count": 0,
                    "first_seen": event.timestamp,
                    "last_seen": event.timestamp,
                    "sources": set(),
                    "avg_processing_time": 0.0,
                }

            metrics = self._event_metrics[event_type_str]
            metrics["count"] += 1
            metrics["last_seen"] = event.timestamp
            metrics["sources"].add(event.source)

    def get_event_metrics(self, event_type: EventType | str | None = None) -> dict[str, Any]:
        """Get event metrics.

        Args:
            event_type: Specific event type to get metrics for, or None for all

        Returns:
            Dictionary of event metrics
        """
        if not self._metrics_enabled:
            return {"error": "Metrics collection is disabled"}

        if event_type is None:
            # Convert sets to lists for JSON serialization
            result = {}
            for et, metrics in self._event_metrics.items():
                result[et] = {**metrics, "sources": list(metrics["sources"])}
            return result

        event_type_str = event_type.value if isinstance(event_type, EventType) else str(event_type)
        metrics = self._event_metrics.get(event_type_str, {})
        if "sources" in metrics:
            metrics = {**metrics, "sources": list(metrics["sources"])}
        return metrics

    def reset_metrics(self) -> None:
        """Reset all event metrics."""
        self._event_metrics.clear()


# Global event bus instances
event_bus = EventBus()
enhanced_event_bus = EnhancedEventBus()


# Helper functions for common operations
@overload
def subscribe(
    event_type: EventType | str | None = None,
    handler: EventHandler | None = None,
    *,
    priority: int = 0,
    filter_fn: Callable[[Event], bool] | None = None,
) -> Callable[[EventHandler], EventHandler]: ...


@overload
def subscribe(
    handler: EventHandler,
) -> EventHandler: ...


def subscribe(*args: Any, **kwargs: Any) -> Any:
    """
    Subscribe to events using the global event bus.

    This function can be used as a decorator or called directly.

    Examples:
        # As a decorator
        @subscribe(EventType.WORKFLOW_STARTED)
        async def on_workflow_started(event: Event) -> None:
            print(f"Workflow started: {event.data}")

        # As a direct call
        def on_step_completed(event: Event) -> None:
            print(f"Step completed: {event.data}")

        subscribe(EventType.STEP_COMPLETED, on_step_completed)
    """
    return event_bus.subscribe(*args, **kwargs)


def publish(event: Event | str, **kwargs: Any) -> Event | asyncio.Task[Event]:
    """
    Publish an event using the global event bus.

    This is a synchronous wrapper around the async publish method. It will run the
    async code in the current event loop if one exists, or create a new one.

    Args:
        event: Event instance or event type string
        **kwargs: Additional data for the event

    Returns:
        The event object after processing, or a Task if running in an async context

    Raises:
        RuntimeError: If called from a running event loop and there's an error
    """
    try:
        loop = asyncio.get_running_loop()
        # We're in a running event loop, schedule the coroutine
        if loop.is_running():
            # Create a task and return it immediately
            # The caller should await this task if they need the result
            return loop.create_task(event_bus.publish(event, **kwargs))
    except RuntimeError:
        # No running loop, create a new one
        return asyncio.run(event_bus.publish(event, **kwargs))

    # If we get here, we have a loop but it's not running
    return loop.run_until_complete(event_bus.publish(event, **kwargs))


def unsubscribe(
    event_type: EventType | str | None,
    handler: EventHandler,
) -> None:
    """
    Unsubscribe a handler using the global event bus.

    Args:
        event_type: The event type to unsubscribe from, or None for all events
        handler: The handler function to remove
    """
    event_bus.unsubscribe(event_type, handler)


# Event Factory Functions


def create_component_event(
    event_type: EventType,
    component_type: str,
    component_id: str,
    operation: str,
    source: str,
    **data: Any,
) -> ComponentEvent:
    """Create a component-related event.

    Args:
        event_type: Type of the event
        component_type: Type of component (DGM, OpenEvolve, SEAL (Self-Adapting Language Models))
        component_id: Unique identifier for the component
        operation: Operation being performed
        source: Source of the event
        **data: Additional event data

    Returns:
        ComponentEvent instance
    """
    return ComponentEvent(
        event_type=event_type,
        source=source,
        data=data,
        component_type=component_type,
        component_id=component_id,
        operation=operation,
    )


def create_error_event(
    error: Exception | str,
    source: str,
    event_type: EventType = EventType.ERROR_OCCURRED,
    severity: str = "error",
    recoverable: bool = True,
    **context: Any,
) -> ErrorEvent:
    """Create an error event from an exception or error message.

    Args:
        error: Exception instance or error message string
        source: Source of the error
        event_type: Type of error event
        severity: Severity level (warning, error, critical)
        recoverable: Whether the error is recoverable
        **context: Additional context data

    Returns:
        ErrorEvent instance
    """
    import traceback

    if isinstance(error, Exception):
        error_type = type(error).__name__
        error_message = str(error)
        stack_trace = traceback.format_exc()
    else:
        error_type = "Error"
        error_message = str(error)
        stack_trace = ""

    return ErrorEvent(
        event_type=event_type,
        source=source,
        data=context,
        error_type=error_type,
        error_message=error_message,
        stack_trace=stack_trace,
        severity=severity,
        recoverable=recoverable,
    )


def create_progress_event(
    current: int,
    total: int,
    stage: str,
    source: str,
    message: str = "",
    event_type: EventType = EventType.PROGRESS_UPDATE,
    **data: Any,
) -> ProgressEvent:
    """Create a progress tracking event.

    Args:
        current: Current progress value
        total: Total expected value
        stage: Current stage or phase
        source: Source of the progress update
        message: Optional progress message
        event_type: Type of progress event
        **data: Additional event data

    Returns:
        ProgressEvent instance
    """
    return ProgressEvent(
        event_type=event_type,
        source=source,
        data=data,
        current=current,
        total=total,
        stage=stage,
        message=message,
    )


def create_metrics_event(
    metrics: dict[str, Any],
    source: str,
    event_type: EventType = EventType.METRICS_COLLECTED,
    severity: str = "info",
    threshold_exceeded: bool = False,
    **context: Any,
) -> MetricsEvent:
    """Create a metrics collection event.

    Args:
        metrics: Dictionary of metric values
        source: Source of the metrics
        event_type: Type of metrics event
        severity: Severity level
        threshold_exceeded: Whether any thresholds were exceeded
        **context: Additional context data

    Returns:
        MetricsEvent instance
    """
    return MetricsEvent(
        event_type=event_type,
        source=source,
        data=context,
        metrics=metrics,
        threshold_exceeded=threshold_exceeded,
        severity=severity,
    )


def create_state_change_event(
    old_state: str,
    new_state: str,
    entity_type: str,
    entity_id: str,
    source: str,
    event_type: EventType = EventType.STATE_CHANGED,
    **data: Any,
) -> StateChangeEvent:
    """Create a state change event.

    Args:
        old_state: Previous state
        new_state: New state
        entity_type: Type of entity (pipeline, component, workflow)
        entity_id: Unique identifier for the entity
        source: Source of the state change
        event_type: Type of state change event
        **data: Additional event data

    Returns:
        StateChangeEvent instance
    """
    return StateChangeEvent(
        event_type=event_type,
        source=source,
        data=data,
        old_state=old_state,
        new_state=new_state,
        entity_type=entity_type,
        entity_id=entity_id,
    )


# Event Filtering Utilities


def create_event_filter(
    event_types: list[EventType | str] | None = None,
    sources: list[str] | None = None,
    severity_levels: list[str] | None = None,
    custom_filter: Callable[[Event], bool] | None = None,
) -> Callable[[Event], bool]:
    """Create a composite event filter function.

    Args:
        event_types: List of event types to include
        sources: List of sources to include
        severity_levels: List of severity levels to include
        custom_filter: Additional custom filter function

    Returns:
        Filter function that returns True if event should be processed
    """

    def filter_fn(event: Event) -> bool:
        # Check event type
        if event_types is not None:
            event_type_str = (
                event.event_type.value
                if isinstance(event.event_type, EventType)
                else str(event.event_type)
            )
            type_strs = [et.value if isinstance(et, EventType) else str(et) for et in event_types]
            if event_type_str not in type_strs:
                return False

        # Check source
        if sources is not None and event.source not in sources:
            return False

        # Check severity (for events that have severity)
        if severity_levels is not None:
            event_severity = event.data.get("severity")
            if event_severity and event_severity not in severity_levels:
                return False

        # Apply custom filter
        if custom_filter is not None and not custom_filter(event):
            return False

        return True

    return filter_fn


# Event Publishing Helpers


async def publish_component_lifecycle_event(
    component_type: str,
    component_id: str,
    lifecycle_event: str,
    source: str,
    **data: Any,
) -> Event:
    """Publish a component lifecycle event.

    Args:
        component_type: Type of component
        component_id: Component identifier
        lifecycle_event: Lifecycle event (started, stopped, paused, etc.)
        source: Event source
        **data: Additional event data

    Returns:
        Published event
    """
    # Map lifecycle events to EventType
    lifecycle_map = {
        "started": EventType.COMPONENT_STARTED,
        "stopped": EventType.COMPONENT_STOPPED,
        "paused": EventType.COMPONENT_PAUSED,
        "resumed": EventType.COMPONENT_RESUMED,
        "failed": EventType.COMPONENT_FAILED,
        "ready": EventType.COMPONENT_READY,
    }

    event_type = lifecycle_map.get(lifecycle_event, EventType.COMPONENT_STATUS_CHANGED)

    event = create_component_event(
        event_type=event_type,
        component_type=component_type,
        component_id=component_id,
        operation=lifecycle_event,
        source=source,
        **data,
    )

    return await event_bus.publish(event)


async def publish_pipeline_stage_event(
    stage: str,
    status: str,
    source: str,
    progress: dict[str, Any] | None = None,
    **data: Any,
) -> Event:
    """Publish a pipeline stage event.

    Args:
        stage: Pipeline stage name
        status: Stage status (started, completed, failed)
        source: Event source
        progress: Optional progress information
        **data: Additional event data

    Returns:
        Published event
    """
    # Map stage status to EventType
    stage_map = {
        "started": EventType.PIPELINE_STAGE_STARTED,
        "completed": EventType.PIPELINE_STAGE_COMPLETED,
        "failed": EventType.PIPELINE_STAGE_FAILED,
    }

    event_type = stage_map.get(status, EventType.PIPELINE_STAGE_STARTED)

    event_data = {"stage": stage, "status": status, **data}
    if progress:
        event_data["progress"] = progress

    event = Event(
        event_type=event_type,
        source=source,
        data=event_data,
    )

    return await event_bus.publish(event)


# Export all public symbols
__all__ = [
    # Enums
    "EventType",
    # Event classes
    "Event",
    "ComponentEvent",
    "MetricsEvent",
    "ErrorEvent",
    "ProgressEvent",
    "StateChangeEvent",
    # Event bus classes
    "EventBus",
    "EnhancedEventBus",
    # Global instances
    "event_bus",
    "enhanced_event_bus",
    # Helper functions
    "subscribe",
    "publish",
    "unsubscribe",
    # Factory functions
    "create_component_event",
    "create_error_event",
    "create_progress_event",
    "create_metrics_event",
    "create_state_change_event",
    # Utility functions
    "create_event_filter",
    "publish_component_lifecycle_event",
    "publish_pipeline_stage_event",
    # Type aliases
    "EventHandler",
]
