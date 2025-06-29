"""
End-to-end workflow tests for SEAL components.

Tests complete workflows including program evaluation, optimization,
and interaction with external services.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Test constants
TEST_FITNESS = 0.9
TEST_ACCURACY = 0.95
TEST_LATENCY = 0.1
TEST_POPULATION_SIZE = 10
TEST_MAX_GENERATIONS = 5
TEST_MUTATION_RATE = 0.1
TEST_CROSSOVER_RATE = 0.8

# Test constants for error recovery test
ERROR_ITERATION = 2  # The iteration where we'll simulate an error
TOTAL_ITERATIONS = 4  # Total number of iterations to run
EXPECTED_SUCCESSFUL_ITERATIONS = 3  # Expected successful iterations (one fails)

# Mock external dependencies
sys.modules["docker"] = MagicMock()
sys.modules["docker.errors"] = MagicMock()

from evoseal.integration.seal.seal_interface import SEALInterface, SEALProvider
from evoseal.models import Program


# Create a mock provider class that implements the required interface
class MockSEALProvider:
    """Mock SEAL provider for testing."""

    def __init__(self):
        self.submit_prompt = AsyncMock(return_value="dummy response")
        self.parse_response = AsyncMock(
            return_value={
                "fitness": TEST_FITNESS,
                "metrics": {"accuracy": TEST_ACCURACY, "latency": TEST_LATENCY},
                "passed": True,
            }
        )


# Mock the workflow components
class SEALWorkflow:
    """Mock SEAL workflow for testing."""

    def __init__(self, config, seal_provider, initial_program):
        self.config = config
        # Create a real SEALInterface with our mock provider
        self.seal_interface = SEALInterface(provider=seal_provider)
        self.initial_program = initial_program
        self.results = []

    async def run(self):
        """Run the workflow."""
        for i in range(self.config.get("max_iterations", 3)):
            try:
                result = await self.seal_interface.submit(f"Iteration {i}")
                self.results.append(result)
            except Exception as e:
                self.results.append({"error": str(e)})
                raise

        return {
            "best_program": Program(id="best_prog", code=self.initial_program, language="python"),
            "final_metrics": self.results[-1] if self.results else {},
        }


@pytest.fixture
def temp_workdir():
    """Create a temporary working directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_seal_provider():
    """Create a mock SEAL provider with realistic responses."""
    # Create a mock that properly implements the async interface
    mock = MockSEALProvider()
    return mock


@pytest.fixture
def workflow_config(temp_workdir):
    """Create a workflow configuration for testing."""
    return {
        "workdir": str(temp_workdir),
        "max_iterations": 3,
        "population_size": 5,
        "mutation_rate": 0.1,
        "crossover_rate": 0.8,
    }


@pytest.mark.asyncio
async def test_seal_workflow_execution(workflow_config, mock_seal_provider):
    """Test execution of a complete SEAL workflow."""
    # Create a simple test program
    initial_program = """
    def process_data(data):
        return [x * 2 for x in data]
    """

    # Set up mock responses
    mock_seal_provider.parse_response.side_effect = [
        {"fitness": 0.8, "metrics": {"accuracy": 0.85}, "passed": True},
        {"fitness": TEST_FITNESS, "metrics": {"accuracy": 0.92}, "passed": True},
        {"fitness": 0.95, "metrics": {"accuracy": 0.96}, "passed": True},
    ]

    # Initialize workflow
    workflow = SEALWorkflow(
        config=workflow_config,
        seal_provider=mock_seal_provider,
        initial_program=initial_program,
    )

    # Run the workflow
    result = await workflow.run()

    # Verify results
    assert result is not None
    assert "best_program" in result
    assert "final_metrics" in result
    assert isinstance(result["final_metrics"], dict)

    # Verify SEAL provider was called the expected number of times
    assert mock_seal_provider.submit_prompt.await_count == workflow_config["max_iterations"]
    assert mock_seal_provider.parse_response.await_count == workflow_config["max_iterations"]


@pytest.mark.asyncio
async def test_workflow_with_error_recovery(workflow_config):
    """Test workflow error handling and recovery."""
    # Create a mock provider for this specific test
    mock_provider = MockSEALProvider()

    # Track calls to mock_parse_response
    call_count = 0

    # Define the mock parse_response function
    async def mock_parse_response(response):
        nonlocal call_count
        call_count += 1
        print(f"\n=== Mock parse_response called, call_count={call_count} ===")
        if call_count == ERROR_ITERATION:  # Second call fails
            print("=== Raising simulated error ===")
            raise Exception("Simulated evaluation error")
        print("=== Returning success response ===")
        return {
            "fitness": TEST_FITNESS,
            "metrics": {"accuracy": TEST_ACCURACY, "latency": TEST_LATENCY},
            "passed": True,
        }

    # Replace the mock's parse_response with our custom one
    mock_provider.parse_response.side_effect = mock_parse_response

    # Initialize workflow
    workflow = SEALWorkflow(
        config=workflow_config,
        seal_provider=mock_provider,
        initial_program="def test(): return 42",
    )

    print("\n=== Starting workflow execution ===")
    result = await workflow.run()
    print(f"\n=== Workflow completed successfully: {result} ===")

    print("\n=== Workflow execution completed ===")
    print(f"call_count: {call_count}")
    print(f"submit_prompt.await_count: {mock_provider.submit_prompt.await_count}")
    print(f"parse_response.await_count: {mock_provider.parse_response.await_count}")
    print(f"workflow.results length: {len(workflow.results)}")

    # Verify the workflow completed successfully
    assert result is not None
    assert "best_program" in result
    assert "final_metrics" in result
    assert isinstance(result["final_metrics"], dict)

    # The workflow should have completed all iterations despite the error
    assert (
        call_count == TOTAL_ITERATIONS
    ), f"Expected {TOTAL_ITERATIONS} total calls, got {call_count}"  # 4 calls in total
    assert (
        mock_provider.submit_prompt.await_count == TOTAL_ITERATIONS
    ), f"Expected {TOTAL_ITERATIONS} submit_prompt calls, got {mock_provider.submit_prompt.await_count}"
    assert (
        mock_provider.parse_response.await_count == TOTAL_ITERATIONS
    ), f"Expected {TOTAL_ITERATIONS} parse_response calls, got {mock_provider.parse_response.await_count}"
    assert (
        len(workflow.results) == EXPECTED_SUCCESSFUL_ITERATIONS
    ), f"Expected {EXPECTED_SUCCESSFUL_ITERATIONS} successful results, got {len(workflow.results)}"  # 3 results (one error was caught and handled)


# Add more test cases for specific workflow scenarios
