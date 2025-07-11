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

    # Step events
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"

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


# Define the handler type after Event is defined
EventHandler: TypeAlias = Union[
    Callable[[Event], None],
    Callable[[Event], Awaitable[None]],
    Callable[[Event], Coroutine[Any, Any, None]],
    Callable[[Event], Optional[Awaitable[None]]],
]


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


# Global event bus instance
event_bus = EventBus()


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
