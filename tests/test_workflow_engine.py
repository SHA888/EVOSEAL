"""Unit tests for the WorkflowEngine class."""

from unittest.mock import MagicMock

import pytest

from evoseal.core.workflow import WorkflowEngine, WorkflowStatus


class TestWorkflowEngine:
    """Test suite for WorkflowEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a fresh WorkflowEngine instance for each test."""
        return WorkflowEngine()

    @pytest.fixture
    def mock_component(self):
        """Create a mock component for testing."""
        return MagicMock()

    def test_initialization(self, engine):
        """Test that the engine initializes correctly."""
        assert engine.get_status() == WorkflowStatus.IDLE
        assert len(engine.components) == 0
        assert len(engine.workflows) == 0

    def test_register_component(self, engine, mock_component):
        """Test component registration."""
        engine.register_component("test", mock_component)
        assert "test" in engine.components
        assert engine.components["test"] == mock_component

    def test_define_workflow(self, engine):
        """Test workflow definition."""
        workflow_steps = [{"name": "step1", "component": "test"}]
        engine.define_workflow("test_workflow", workflow_steps)

        assert "test_workflow" in engine.workflows
        assert engine.workflows["test_workflow"]["steps"] == workflow_steps
        assert engine.workflows["test_workflow"]["status"] == WorkflowStatus.PENDING

    def test_execute_workflow_success(self, engine, mock_component):
        """Test successful workflow execution."""
        # Setup
        mock_component.test_method.return_value = "result"
        engine.register_component("test", mock_component)

        workflow = [{"name": "step1", "component": "test", "method": "test_method"}]
        engine.define_workflow("test_flow", workflow)

        # Execute
        result = engine.execute_workflow("test_flow")

        # Verify
        assert result is True
        assert engine.get_status() == WorkflowStatus.COMPLETED
        mock_component.test_method.assert_called_once()

    def test_execute_workflow_nonexistent(self, engine):
        """Test executing non-existent workflow raises KeyError."""
        with pytest.raises(KeyError, match="Workflow 'nonexistent' not found"):
            engine.execute_workflow("nonexistent")

    def test_event_handling(self, engine, mock_component):
        """Test event handling during workflow execution."""
        # Setup
        handler = MagicMock()
        engine.register_event_handler("workflow_started", handler)

        workflow = [{"name": "step1", "component": "test"}]
        engine.define_workflow("test_flow", workflow)

        # Execute
        engine.execute_workflow("test_flow")

        # Verify event was triggered
        handler.assert_called_once()

    def test_error_handling(self, engine, mock_component):
        """Test error handling during workflow execution."""
        # Setup failing component
        mock_component.test_method.side_effect = Exception("Test error")
        engine.register_component("test", mock_component)

        workflow = [{"name": "failing_step", "component": "test", "method": "test_method"}]
        engine.define_workflow("failing_flow", workflow)

        # Execute and verify failure
        result = engine.execute_workflow("failing_flow")
        assert result is False
        assert engine.get_status() == WorkflowStatus.FAILED
