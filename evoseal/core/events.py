"""
Event system for the EVOSEAL workflow engine.

This module provides a flexible event system supporting both synchronous and
asynchronous event handling, with features like event filtering, propagation
control, and error handling.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
    cast,
    overload,
)

logger = logging.getLogger(__name__)

# Type variables for better type hints
T = TypeVar("T")
EventHandler = Callable[[Any], Union[None, Awaitable[None]]]


class EventType(Enum):
    """Types of events in the workflow system."""

    # Workflow events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"

    # Step events
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"

    # Custom events
    CUSTOM = "custom"


@dataclass
class Event:
    """Base class for all workflow events."""

    event_type: Union[EventType, str]
    source: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    _stop_propagation: bool = field(default=False, init=False)

    def stop_propagation(self) -> None:
        """Stop further processing of this event."""
        self._stop_propagation = True


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
        self._handlers: Dict[str, List[Dict[str, Any]]] = {}
        self._default_handlers: List[Dict[str, Any]] = []

    def subscribe(
        self,
        event_type: Union[EventType, str, None] = None,
        handler: Optional[Callable[[Event], Optional[Awaitable[None]]]] = None,
        *,
        priority: int = 0,
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> Union[
        Callable[[], None],
        Callable[
            [Callable[[Event], Optional[Awaitable[None]]]],
            Callable[[Event], Optional[Awaitable[None]]],
        ],
    ]:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: The type of event to subscribe to, or None for all events
            handler: The callback function to handle the event
            priority: Higher priority handlers are called first (default: 0)
            filter_fn: Optional function to filter which events are handled

        Returns:
            A function that can be used to unsubscribe
        """

        def decorator(
            handler_func: Callable[[Event], Optional[Awaitable[None]]],
        ) -> Callable[[Event], Optional[Awaitable[None]]]:
            nonlocal event_type
            event_str = (
                event_type.value
                if isinstance(event_type, EventType)
                else str(event_type) if event_type is not None else None
            )
            # Determine if the handler is async
            is_async = asyncio.iscoroutinefunction(handler_func) or (
                hasattr(handler_func, "__code__")
                and asyncio.iscoroutinefunction(handler_func.__code__)
            )
            
            handler_info = {
                "handler": handler_func,
                "priority": priority,
                "filter": filter_fn,
                "is_async": is_async,
            }

            if event_type is None:
                self._default_handlers.append(handler_info)
                self._default_handlers.sort(key=lambda x: x["priority"], reverse=True)

                def unsubscribe() -> None:
                    self._default_handlers = [
                        h
                        for h in self._default_handlers
                        if h["handler"] != handler_func
                    ]

                # Store the unsubscribe function
                if not hasattr(handler_func, "_unsubscribe"):
                    handler_func._unsubscribe = unsubscribe  # type: ignore

                return handler_func
            else:
                if event_str is None:
                    raise ValueError(
                        "Event type cannot be None when using a string event type"
                    )

                if event_str not in self._handlers:
                    self._handlers[event_str] = []
                self._handlers[event_str].append(handler_info)
                self._handlers[event_str].sort(
                    key=lambda x: x["priority"], reverse=True
                )

                def unsubscribe() -> None:
                    if event_str in self._handlers:
                        self._handlers[event_str] = [
                            h
                            for h in self._handlers[event_str]
                            if h["handler"] != handler_func
                        ]

                # Store the unsubscribe function
                if not hasattr(handler_func, "_unsubscribe"):
                    handler_func._unsubscribe = unsubscribe  # type: ignore

                return handler_func

        if handler is not None:
            decorator(handler)
            return lambda: self.unsubscribe(event_type, handler)

        def wrapper(
            handler_func: Callable[[Event], Optional[Awaitable[None]]],
        ) -> Callable[[Event], Optional[Awaitable[None]]]:
            decorator(handler_func)
            return handler_func

        return wrapper

    def unsubscribe(
        self,
        event_type: Union[EventType, str, None],
        handler: Callable[[Event], Optional[Awaitable[None]]],
    ) -> None:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: The event type to unsubscribe from, or None for all events
            handler: The handler function to remove
        """
        if event_type is None:
            self._default_handlers = [
                h for h in self._default_handlers if h["handler"] != handler
            ]
        else:
            event_type_str = (
                event_type.value if isinstance(event_type, EventType) else event_type
            )
            if event_type_str in self._handlers:
                self._handlers[event_type_str] = [
                    h for h in self._handlers[event_type_str] if h["handler"] != handler
                ]

    async def publish(self, event: Union[Event, str], **kwargs: Any) -> Event:
        """
        Publish an event to all subscribers.

        Args:
            event: Event instance or event type string
            **kwargs: Additional data for the event

        Returns:
            The event object after processing
        """
        if not isinstance(event, Event):
            event = Event(
                event_type=event,
                source=kwargs.get("source", "unknown"),
                data=kwargs.get("data", {}),
                context=kwargs.get("context", {}),
            )

        # Get all relevant handlers
        handlers: List[Dict[str, Any]] = []

        # Get specific handlers for this event type
        event_type_str = (
            event.event_type.value
            if isinstance(event.event_type, EventType)
            else event.event_type
        )
        if event_type_str in self._handlers:
            handlers.extend(self._handlers[event_type_str])

        # Add default handlers (for all event types)
        handlers.extend(self._default_handlers)

        # Execute handlers in order of priority
        for handler_info in handlers:
            if event._stop_propagation:
                break

            # Skip if filter doesn't pass
            if handler_info["filter"] and not handler_info["filter"](event):
                continue

            try:
                if handler_info["is_async"]:
                    await handler_info["handler"](event)
                else:
                    handler_info["handler"](event)
            except Exception as e:
                logger.error(
                    f"Error in {handler_info['handler'].__name__} "
                    f"for event {event.event_type}: {str(e)}",
                    exc_info=True,
                )

        return event


# Global event bus instance
event_bus = EventBus()


# Helper functions for common operations
@overload
def subscribe(
    event_type: Union[EventType, str, None] = None,
    handler: Optional[Callable[[Event], Optional[Awaitable[None]]]] = None,
    *,
    priority: int = 0,
    filter_fn: Optional[Callable[[Event], bool]] = None,
) -> Union[
    Callable[[], None],
    Callable[
        [Callable[[Event], Optional[Awaitable[None]]]],
        Callable[[Event], Optional[Awaitable[None]]],
    ],
]: ...


@overload
def subscribe(
    handler: Callable[[Event], Optional[Awaitable[None]]],
) -> Callable[[Event], Optional[Awaitable[None]]]: ...


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


def publish(event: Union[Event, str], **kwargs: Any) -> Event:
    """
    Publish an event using the global event bus.

    This is a synchronous wrapper around the async publish method. It will run the
    async code in the current event loop if one exists, or create a new one.

    Args:
        event: Event instance or event type string
        **kwargs: Additional data for the event

    Returns:
        The event object after processing

    Raises:
        RuntimeError: If called from a running event loop and there's an error
    """

    try:
        loop = asyncio.get_running_loop()
        # We're in a running event loop, schedule the coroutine
        if loop.is_running():
            # Create a task and return the event immediately
            # The caller should handle the task appropriately
            return loop.create_task(event_bus.publish(event, **kwargs))
    except RuntimeError:
        # No running loop, create a new one
        return asyncio.run(event_bus.publish(event, **kwargs))
    
    # If we get here, we have a loop but it's not running
    return loop.run_until_complete(event_bus.publish(event, **kwargs))


def unsubscribe(
    event_type: Union[EventType, str, None],
    handler: Callable[[Event], Optional[Awaitable[None]]],
) -> None:
    """
    Unsubscribe a handler using the global event bus.

    Args:
        event_type: The event type to unsubscribe from, or None for all events
        handler: The handler function to remove
    """
    event_bus.unsubscribe(event_type, handler)
