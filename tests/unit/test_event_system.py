"""Tests for the event system functionality."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from evoseal.core.events import Event, EventBus, EventType
from evoseal.core.workflow import StepConfig, WorkflowEngine


class TestEventSystem:
    """Test the event system functionality."""

    def test_event_creation(self):
        """Test creating an event with data."""
        data = {"key": "value"}
        event = Event("test_event", "test_source", data)

        assert event.event_type == "test_event"
        assert event.source == "test_source"
        assert event.data == data
        assert isinstance(event.timestamp, float)
        assert not event._stop_propagation

        # Test stop_propagation
        event.stop_propagation()
        assert event._stop_propagation is True

    def test_event_bus_subscribe(self) -> None:
        """Test subscribing to events."""
        # Initialize test objects
        bus = EventBus()
        calls = []

        # Define a handler function with proper type hints
        def handler(event: Event) -> None:
            calls.append(event)

        # Test subscribing with the decorator pattern using event type
        @bus.subscribe(EventType.WORKFLOW_STARTED)
        def workflow_started_handler(event: Event) -> None:
            handler(event)

        # Create an event
        event = Event(EventType.WORKFLOW_STARTED, "test_source", {"key": "value"})

        # Publish the event to trigger the handler
        asyncio.run(bus.publish(event))

        # Verify the handler was called
        assert len(calls) == 1
        assert calls[0] is event

        # Test direct subscription
        calls = []
        unsubscribe = bus.subscribe(EventType.WORKFLOW_COMPLETED, handler)

        # Create and publish another event
        event2 = Event(EventType.WORKFLOW_COMPLETED, "test_source", {"key": "value2"})
        asyncio.run(bus.publish(event2))

        # Verify the handler was called
        assert len(calls) == 1
        assert calls[0] is event2

        # Clean up
        unsubscribe()

        # Test that handler is no longer called after unsubscribing
        calls = []
        asyncio.run(bus.publish(event2))
        assert len(calls) == 0

    @pytest.mark.asyncio
    async def test_event_bus_publish_sync(self):
        """Test publishing events synchronously."""
        bus = EventBus()
        # Create a properly typed mock handler
        handler = MagicMock(spec=Callable[[Event], None])

        # Subscribe handler
        bus.subscribe("test_event", handler)

        # Publish event
        event_data = {"key": "value"}
        event = Event("test_event", "test_source", event_data)
        await bus.publish(event)

        # Verify handler was called with the correct event
        handler.assert_called_once()
        called_event = handler.call_args[0][0]
        assert isinstance(called_event, Event)
        assert called_event.data == event_data

    @pytest.mark.asyncio  # type: ignore[misc]
    async def test_event_bus_publish_async(self) -> None:
        """Test publishing events asynchronously."""
        bus = EventBus()

        # Track calls to verify async behavior
        calls = []

        # Create a real async function with the right signature
        async def async_mock_handler(event: Event) -> None:
            calls.append(event)

        # Use the real async function for subscription
        bus.subscribe("test_event", async_mock_handler)

        # Publish event
        event_data = {"key": "value"}
        event = Event("test_event", "test_source", event_data)
        await bus.publish(event)

        # Verify the handler was called with the correct event
        assert len(calls) == 1
        called_event = calls[0]
        assert isinstance(called_event, Event)
        assert called_event.data == event_data

    @pytest.mark.asyncio
    async def test_event_priority(self):
        """Test event handler priority ordering."""
        bus = EventBus()
        calls = []

        # Add handlers with different priorities
        @bus.subscribe("test_event", priority=1)
        def low_priority(event):
            calls.append("low")

        @bus.subscribe("test_event", priority=10)
        def high_priority(event):
            calls.append("high")

        # Publish event
        await bus.publish(Event("test_event", "test_source", {}))

        # Verify handlers called in priority order
        assert calls == ["high", "low"]

    @pytest.mark.asyncio
    async def test_event_filtering(self):
        """Test event filtering."""
        bus = EventBus()
        handler = AsyncMock()

        # Subscribe with filter
        def filter_fn(event):
            return event.data.get("include", False)

        bus.subscribe("test_event", handler, filter_fn=filter_fn)

        # Publish event that should be filtered out
        await bus.publish(Event("test_event", "test_source", {"include": False}))
        handler.assert_not_called()

        # Publish event that should be handled
        await bus.publish(Event("test_event", "test_source", {"include": True}))
        handler.assert_awaited_once()

    @pytest.fixture  # type: ignore[misc]
    def test_workflow_engine(self) -> tuple[WorkflowEngine, type]:
        """Fixture to set up a test workflow engine with a test component."""

        # Define test component
        class TestComponent:
            async def process(self, test: str) -> dict[str, Any]:
                return {"processed": True, "test_data": test}

        # Set up engine and register component
        engine = WorkflowEngine()
        engine.register_component("test", TestComponent())

        return engine, TestComponent

    @pytest.fixture  # type: ignore[misc]
    def workflow_definition(self) -> list[StepConfig]:
        """Fixture providing a simple workflow definition."""
        return [
            {
                "name": "test_step",
                "component": "test",
                "method": "process",
                "params": {"test": "test_data"},
            }
        ]

    @pytest.fixture  # type: ignore[misc]
    def event_handlers(
        self,
    ) -> tuple[list[tuple[str, str]], dict[str, Callable[..., None]]]:
        """Fixture to set up event handlers and track received events."""
        events_received: list[tuple[str, str]] = []

        def on_start(event: Event) -> None:
            events_received.append(("started", event.data.get("workflow", "")))

        def on_step_start(event: Event) -> None:
            events_received.append(("step_started", event.data.get("step", "")))

        def on_step_complete(event: Event) -> None:
            events_received.append(("step_completed", event.data.get("step", "")))

        def on_complete(event: Event) -> None:
            events_received.append(("completed", event.data.get("workflow", "")))

        handlers = {
            "on_start": on_start,
            "on_step_start": on_step_start,
            "on_step_complete": on_step_complete,
            "on_complete": on_complete,
        }

        return events_received, handlers

    @pytest.mark.asyncio  # type: ignore[misc]
    async def test_workflow_event_registration(
        self,
        test_workflow_engine: tuple[WorkflowEngine, type],
        workflow_definition: list[StepConfig],
        event_handlers: tuple[list[tuple[str, str]], dict[str, Callable[..., None]]],
    ) -> None:
        """Test that workflow events are properly registered and handled."""
        engine, _ = test_workflow_engine
        events_received, handlers = event_handlers

        # Define workflow
        engine.define_workflow("test_workflow", workflow_definition)

        # Register event handlers
        engine.register_event_handler(EventType.WORKFLOW_STARTED, handlers["on_start"])
        engine.register_event_handler(EventType.STEP_STARTED, handlers["on_step_start"])
        engine.register_event_handler(EventType.STEP_COMPLETED, handlers["on_step_complete"])
        engine.register_event_handler(EventType.WORKFLOW_COMPLETED, handlers["on_complete"])

        # Run workflow
        result = await engine.execute_workflow_async("test_workflow")

        # Verify execution and events
        min_expected_events = (
            4  # WORKFLOW_STARTED, STEP_STARTED, STEP_COMPLETED, WORKFLOW_COMPLETED
        )
        assert result is True
        assert len(events_received) >= min_expected_events

    @pytest.mark.asyncio  # type: ignore[misc]
    async def test_workflow_event_types(
        self,
        test_workflow_engine: tuple[WorkflowEngine, type],
        workflow_definition: list[StepConfig],
        event_handlers: tuple[list[tuple[str, str]], dict[str, Callable[..., None]]],
    ) -> None:
        """Test that all expected workflow event types are triggered."""
        engine, _ = test_workflow_engine
        events_received, handlers = event_handlers

        # Set up workflow and handlers
        engine.define_workflow("test_workflow", workflow_definition)
        engine.register_event_handler(EventType.WORKFLOW_STARTED, handlers["on_start"])
        engine.register_event_handler(EventType.STEP_STARTED, handlers["on_step_start"])
        engine.register_event_handler(EventType.STEP_COMPLETED, handlers["on_step_complete"])
        engine.register_event_handler(EventType.WORKFLOW_COMPLETED, handlers["on_complete"])

        # Run workflow
        await engine.execute_workflow_async("test_workflow")

        # Verify all event types were received
        event_types = {e[0] for e in events_received}
        assert "started" in event_types
        assert "step_started" in event_types
        assert "step_completed" in event_types
        assert "completed" in event_types

    @pytest.mark.asyncio  # type: ignore[misc]
    async def test_workflow_event_ordering(
        self,
        test_workflow_engine: tuple[WorkflowEngine, type],
        workflow_definition: list[StepConfig],
        event_handlers: tuple[list[tuple[str, str]], dict[str, Callable[..., None]]],
    ) -> None:
        """Test that workflow events are triggered in the correct order."""
        engine, _ = test_workflow_engine
        events_received, handlers = event_handlers

        # Set up workflow and handlers
        engine.define_workflow("test_workflow", workflow_definition)
        engine.register_event_handler(EventType.WORKFLOW_STARTED, handlers["on_start"])
        engine.register_event_handler(EventType.STEP_STARTED, handlers["on_step_start"])
        engine.register_event_handler(EventType.STEP_COMPLETED, handlers["on_step_complete"])
        engine.register_event_handler(EventType.WORKFLOW_COMPLETED, handlers["on_complete"])

        # Run workflow
        await engine.execute_workflow_async("test_workflow")

        # Verify event ordering
        event_sequence = [e[0] for e in events_received]
        assert event_sequence.index("started") < event_sequence.index("step_started")
        assert event_sequence.index("step_started") < event_sequence.index("step_completed")
        assert event_sequence.index("step_completed") < event_sequence.index("completed")
