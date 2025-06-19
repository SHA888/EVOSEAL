"""Tests for the event system functionality."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from evoseal.core.events import Event, EventBus, EventType
from evoseal.core.workflow import WorkflowEngine


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

    def test_event_bus_subscribe(self):
        """Test subscribing to events."""
        bus = EventBus()
        handler = Mock()

        # Subscribe to specific event
        bus.subscribe("test_event", handler)
        assert "test_event" in bus._handlers
        assert len(bus._handlers["test_event"]) == 1

        # Subscribe to all events
        bus.subscribe(handler=handler)
        assert len(bus._default_handlers) == 1

    @pytest.mark.asyncio
    async def test_event_bus_publish_sync(self):
        """Test publishing events synchronously."""
        bus = EventBus()
        handler = Mock()

        # Subscribe handler
        bus.subscribe("test_event", handler)

        # Publish event
        event_data = {"key": "value"}
        await bus.publish(Event("test_event", "test_source", event_data))

        # Verify handler was called
        handler.assert_called_once()
        assert handler.call_args[0][0].data == event_data

    @pytest.mark.asyncio
    async def test_event_bus_publish_async(self):
        """Test publishing events asynchronously."""
        bus = EventBus()
        handler = AsyncMock()

        # Subscribe async handler
        bus.subscribe("test_event", handler)

        # Publish event
        event_data = {"key": "value"}
        await bus.publish(Event("test_event", "test_source", event_data))

        # Verify async handler was called
        handler.assert_awaited_once()
        assert handler.await_args[0][0].data == event_data

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

    @pytest.mark.asyncio
    async def test_workflow_events(self):
        """Test workflow events using the event bus."""
        engine = WorkflowEngine()

        # Register a test component
        class TestComponent:
            async def process(self, test):
                return {"processed": True, "test_data": test}

        engine.register_component("test", TestComponent())

        # Define a simple workflow
        workflow = [
            {
                "name": "test_step",
                "component": "test",
                "method": "process",
                "params": {"test": "test_data"},
            }
        ]
        engine.define_workflow("test_workflow", workflow)

        # Setup event handlers
        events_received = []

        @engine.register_event_handler(EventType.WORKFLOW_STARTED)
        def on_start(event):
            events_received.append(("started", event.data["workflow"]))

        @engine.register_event_handler(EventType.STEP_STARTED)
        def on_step_start(event):
            events_received.append(("step_started", event.data["step"]))

        @engine.register_event_handler(EventType.STEP_COMPLETED)
        def on_step_complete(event):
            events_received.append(("step_completed", event.data["step"]))

        @engine.register_event_handler(EventType.WORKFLOW_COMPLETED)
        def on_complete(event):
            events_received.append(("completed", event.data["workflow"]))

        # Run the workflow
        result = await engine.execute_workflow_async("test_workflow")

        # Verify results
        assert result is True
        expected_event_count = (
            10  # 3 events for each workflow + 1 for workflow completion
        )
        assert len(events_received) == expected_event_count
        assert events_received[0] == ("started", "test_workflow")
        assert events_received[1] == ("step_started", "test_step")
        assert events_received[2] == ("step_completed", "test_step")
        assert events_received[3] == ("completed", "test_workflow")
