"""Integration tests for the WorkflowEngine class."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from evoseal.core.errors import ValidationError
from evoseal.core.workflow import Event, EventType, WorkflowEngine, WorkflowStatus


class TestWorkflowEngineIntegration:
    """Integration test suite for WorkflowEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a fresh WorkflowEngine instance for each test."""
        return WorkflowEngine()

    @pytest.fixture
    def mock_component(self):
        """Create a mock component for testing."""
        return MagicMock()

    @pytest.fixture
    def async_mock_component(self):
        """Create an async mock component for testing."""
        return AsyncMock()

    @pytest.fixture
    def sample_workflow_steps(self):
        """Return a sample workflow configuration."""
        return [
            {
                "name": "step1",
                "component": "test_component",
                "method": "test_method",
                "params": {"param1": "value1"},
            },
            {
                "name": "step2",
                "component": "test_component",
                "method": "async_test_method",
                "params": {"param2": "value2"},
            },
        ]

    @pytest.mark.asyncio
    async def test_workflow_lifecycle(
        self, engine, mock_component, sample_workflow_steps
    ):
        """Test the complete workflow lifecycle with synchronous and asynchronous steps."""
        # Setup
        mock_component.test_method.return_value = "step1_result"
        engine.register_component("test_component", mock_component)
        engine.define_workflow("test_workflow", sample_workflow_steps)

        # Execute
        success = await engine.execute_workflow_async("test_workflow")

        # Verify
        assert success is True
        assert engine.status == WorkflowStatus.COMPLETED
        mock_component.test_method.assert_called_once_with(param1="value1")

    @pytest.mark.asyncio
    async def test_async_workflow_execution(
        self, engine, async_mock_component, sample_workflow_steps
    ):
        """Test workflow execution with async components."""
        # Setup
        async_mock_component.async_test_method.return_value = "async_result"
        engine.register_component("test_component", async_mock_component)
        engine.define_workflow("test_async_workflow", sample_workflow_steps[1:])

        # Execute
        success = await engine.execute_workflow_async("test_async_workflow")

        # Verify
        assert success is True
        assert engine.status == WorkflowStatus.COMPLETED
        async_mock_component.async_test_method.assert_awaited_once_with(param2="value2")

    @pytest.mark.asyncio
    async def test_workflow_with_event_handlers(
        self, engine, mock_component, sample_workflow_steps
    ):
        """Test workflow execution with event handlers."""
        # Setup
        mock_component.test_method.return_value = "result"
        engine.register_component("test_component", mock_component)
        engine.define_workflow("test_workflow", sample_workflow_steps[:1])

        # Register event handlers
        event_log = []

        @engine.register_event_handler(EventType.WORKFLOW_STARTED)
        def on_workflow_started(event):
            event_log.append(("workflow_started", event.data["workflow"]))

        @engine.register_event_handler(EventType.STEP_COMPLETED)
        def on_step_completed(event):
            event_log.append(("step_completed", event.data["step"]))

        # Execute
        success = await engine.execute_workflow_async("test_workflow")

        # Verify
        expected_event_count = 2  # WORKFLOW_STARTED and STEP_COMPLETED
        assert success is True
        assert len(event_log) == expected_event_count
        assert event_log[0][0] == "workflow_started"
        assert event_log[1][0] == "step_completed"

    @pytest.mark.asyncio
    async def test_workflow_with_failure(self, engine, mock_component):
        """Test workflow execution with a failing step."""
        # Setup
        mock_component.test_method.side_effect = Exception("Test error")
        engine.register_component("test_component", mock_component)
        workflow_steps = [
            {
                "name": "failing_step",
                "component": "test_component",
                "method": "test_method",
            }
        ]
        engine.define_workflow("failing_workflow", workflow_steps)

        # Execute and verify failure
        success = await engine.execute_workflow_async("failing_workflow")
        assert success is False
        assert engine.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_workflow_with_step_dependencies(self, engine, mock_component):
        """Test workflow execution with step dependencies."""
        # Setup
        mock_component.method1.return_value = "result1"
        mock_component.method2.return_value = "result2"
        engine.register_component("test_component", mock_component)

        workflow_steps = [
            {"name": "step1", "component": "test_component", "method": "method1"},
            {
                "name": "step2",
                "component": "test_component",
                "method": "method2",
                "dependencies": ["step1"],
            },
        ]
        engine.define_workflow("dependent_workflow", workflow_steps)

        # Execute
        success = await engine.execute_workflow_async("dependent_workflow")

        # Verify
        assert success is True
        assert engine.status == WorkflowStatus.COMPLETED
        mock_component.method1.assert_called_once()
        mock_component.method2.assert_called_once()
        # Verify order of execution
        mock_calls = mock_component.method_calls
        assert mock_calls[0][0] == "method1"
        assert mock_calls[1][0] == "method2"

    @pytest.mark.asyncio
    async def test_workflow_with_nonexistent_component(self, engine):
        """Test workflow execution with a non-existent component."""
        # Define a workflow that references a non-existent component
        workflow_steps = [
            {
                "name": "invalid_step",
                "component": "nonexistent_component",
                "method": "some_method",
            }
        ]
        engine.define_workflow("invalid_workflow", workflow_steps)

        # Execute the workflow
        success = await engine.execute_workflow_async("invalid_workflow")

        # Verify the workflow failed and the status is set correctly
        assert success is False
        assert engine.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_workflow_with_invalid_step_definition(self, engine):
        """Test workflow execution with an invalid step definition."""
        # Define a workflow with an invalid step (missing required fields)
        workflow_steps = [
            {
                "name": "invalid_step",
                # Missing 'component' and 'method' fields
            }
        ]
        engine.define_workflow("invalid_workflow", workflow_steps)

        # Execute the workflow
        success = await engine.execute_workflow_async("invalid_workflow")

        # Verify the workflow failed and the status is set correctly
        assert success is False
        assert engine.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_workflow_event_publishing(self, engine, mock_component):
        """Test that workflow events are properly published."""
        # Setup
        mock_component.test_method.return_value = "result"
        engine.register_component("test_component", mock_component)

        workflow_steps = [
            {
                "name": "test_step",
                "component": "test_component",
                "method": "test_method",
            }
        ]
        engine.define_workflow("event_workflow", workflow_steps)

        # Track published events and their order
        published_events = []
        event_order = []

        # Create a mock event handler that captures events
        async def event_handler(event):
            event_type = event.event_type
            published_events.append(event_type)
            # Only add to event_order if not already present to avoid duplicates
            if event_type not in event_order:
                event_order.append(event_type)

        # Register a single handler for all events
        engine.event_bus.subscribe(
            event_handler, None
        )  # None means subscribe to all events

        # Execute the workflow
        success = await engine.execute_workflow_async("event_workflow")

        # Verify
        assert success is True

        # Check that we received the expected events in the correct order
        expected_events = [
            EventType.WORKFLOW_STARTED.value,
            EventType.STEP_STARTED.value,
            EventType.STEP_COMPLETED.value,
            EventType.WORKFLOW_COMPLETED.value,
        ]

        # Check that we have exactly the expected number of unique events
        assert len(event_order) == len(
            expected_events
        ), f"Expected {len(expected_events)} unique events, got {len(event_order)}: {event_order}"

        # Check that all expected events are present in the correct order
        for i, expected in enumerate(expected_events):
            assert (
                event_order[i] == expected
            ), f"Expected {expected} at position {i}, got {event_order[i]}"

        # Verify that each event type appears the expected number of times
        # (should be exactly once for each event type)
        event_counts = {
            event: published_events.count(event) for event in set(published_events)
        }
        for event_type, count in event_counts.items():
            assert (
                count == 1
            ), f"Expected {event_type} to appear exactly once, but it appeared {count} times"

    @pytest.mark.asyncio
    async def test_workflow_cleanup(self, engine, mock_component):
        """Test that workflow engine cleanup works as expected."""
        # Register a component and define a workflow
        mock_component.test_method.return_value = "result"
        engine.register_component("test_component", mock_component)

        workflow_steps = [
            {
                "name": "test_step",
                "component": "test_component",
                "method": "test_method",
            }
        ]
        engine.define_workflow("cleanup_workflow", workflow_steps)

        # Create a mock event handler that will be cleaned up
        mock_handler = MagicMock()
        engine.register_event_handler(EventType.WORKFLOW_STARTED)(mock_handler)

        # Execute the workflow
        success = await engine.execute_workflow_async("cleanup_workflow")
        assert success is True

        # Verify the handler was called
        mock_handler.assert_called_once()

        # Clean up
        engine.cleanup()

        # The handler should be unsubscribed, so it shouldn't be called again
        mock_handler.reset_mock()
        await engine.execute_workflow_async("cleanup_workflow")
        mock_handler.assert_not_called()
