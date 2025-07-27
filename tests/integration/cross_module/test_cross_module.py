"""
Integration tests for cross-module interactions.

Tests the interaction between components, including data flow, state management,
and error handling across module boundaries.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Test constants
TEST_FITNESS = 0.9
TEST_ACCURACY = 0.95
TEST_LATENCY = 0.1
TEST_POPULATION_SIZE = 10

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock external dependencies
sys.modules["docker"] = MagicMock()
sys.modules["docker.errors"] = MagicMock()

from evoseal.core.controller import Controller

# Import after path setup
from evoseal.integration.seal.seal_interface import SEALInterface, SEALProvider
from evoseal.models import Program


# Mock the components for testing
class MockController(Controller):
    """Mock Controller for testing."""

    def __init__(self, test_runner: Any, evaluator: Any, logger=None):
        super().__init__(test_runner, evaluator, logger)
        self.seal_interface = None
        self._loop = asyncio.new_event_loop()

    def set_seal_interface(self, seal_interface):
        """Set the SEAL (Self-Adapting Language Models) interface for testing."""
        self.seal_interface = seal_interface

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the controller with the given config."""
        super().initialize(config)

    async def _run_generation_async(self):
        """Run a single generation asynchronously."""
        if self.seal_interface:
            # Simulate calling the SEAL (Self-Adapting Language Models) interface
            response = await self.seal_interface.submit("test prompt")
            return response
        return None

    def run_generation(self) -> dict[str, Any]:
        """Run a single generation and return results."""
        if self._loop.is_running():
            # If we're already in an event loop, use it
            response = self._loop.run_until_complete(self._run_generation_async())
        else:
            # Otherwise, create a new event loop
            response = asyncio.run(self._run_generation_async())
        return response or {
            "success": False,
            "message": "No SEAL (Self-Adapting Language Models) interface configured",
        }


# Mock test runner and evaluator for the controller
class MockTestRunner:
    """Mock TestRunner for testing."""

    def __init__(self):
        self.test_results = {}

    def run_tests(self, generation):
        """Return mock test results."""
        return {"test_result": f"test_result_gen_{generation}"}


class MockEvaluator:
    """Mock Evaluator for testing."""

    def __init__(self):
        self.eval_results = {}

    def evaluate(self, test_results):
        """Return mock evaluation results."""
        return {"eval_result": f"eval_result_{test_results['test_result']}"}


@pytest.fixture
def mock_components():
    """Create mock instances of all components for testing."""
    # Create mock SEAL (Self-Adapting Language Models) interface
    mock_seal = AsyncMock(spec=SEALInterface)
    mock_seal.submit.return_value = {
        "success": True,
        "result": {"fitness": 0.9, "accuracy": 0.95, "latency": 0.1},
    }

    # Create mock test runner and evaluator
    mock_test_runner = MockTestRunner()
    mock_evaluator = MockEvaluator()

    # Create mock controller
    mock_controller = MockController(
        test_runner=mock_test_runner, evaluator=mock_evaluator
    )
    mock_controller.set_seal_interface(mock_seal)

    # Create mock program
    mock_program = Program(
        id="test_prog_1", code="def test(): return 42", language="python"
    )

    return {
        "seal": mock_seal,
        "test_runner": mock_test_runner,
        "evaluator": mock_evaluator,
        "controller": mock_controller,
        "program": mock_program,
    }


@pytest.mark.asyncio
async def test_cross_module_workflow(mock_components):
    """Test the complete workflow across components."""
    mock_seal = mock_components["seal"]
    mock_controller = mock_components["controller"]
    _ = mock_components["program"]  # Keep for test context

    # Initialize the controller
    config = {"population_size": 10, "max_generations": 100}
    mock_controller.initialize(config)

    # Run a test generation
    result = await mock_controller._run_generation_async()

    # Verify the SEAL (Self-Adapting Language Models) interface was called
    mock_seal.submit.assert_called_once()
    assert "test prompt" in mock_seal.submit.call_args[0][0]

    # Verify the result structure
    assert result is not None
    assert "success" in result
    assert result["success"] is True


@pytest.mark.asyncio
async def test_error_handling_across_modules(mock_components):
    """Test error handling across module boundaries."""
    mock_seal = mock_components["seal"]
    mock_controller = mock_components["controller"]

    # Initialize the controller
    config = {"population_size": 10, "max_generations": 100}
    mock_controller.initialize(config)

    # Simulate an error in the SEAL (Self-Adapting Language Models) interface
    mock_seal.submit.side_effect = Exception("Test error")

    # Verify the error is properly handled
    with pytest.raises(Exception) as exc_info:
        await mock_controller._run_generation_async()

    assert "Test error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_data_flow_between_components(mock_components):
    """Test data flow between components."""
    mock_seal = mock_components["seal"]
    mock_controller = mock_components["controller"]
    _ = mock_components["test_runner"]  # Keep for test context
    _ = mock_components["evaluator"]  # Keep for test context

    # Initialize the controller
    config = {"population_size": 10, "max_generations": 100}
    mock_controller.initialize(config)

    # Configure mock responses
    expected_result = {
        "success": True,
        "result": {"fitness": 0.95, "accuracy": 0.98, "latency": 0.08},
    }
    mock_seal.submit.return_value = expected_result

    # Run a test generation
    result = await mock_controller._run_generation_async()

    # Verify data flow
    mock_seal.submit.assert_called_once()
    assert result == expected_result
