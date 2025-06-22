"""
Integration tests for SEAL core functionality.

Tests the core SEAL components including initialization, program evaluation,
and interaction with the evolutionary process.
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock external dependencies
sys.modules["docker"] = MagicMock()
sys.modules["docker.errors"] = MagicMock()

from evoseal.models import Program
from evoseal.integration.seal.seal_interface import SEALInterface, SEALProvider

# Test constants
TEST_FITNESS = 0.9
TEST_ACCURACY = 0.95
TEST_LATENCY = 0.1
TEST_RATE_LIMIT = 10  # requests per second
MIN_EXPECTED_TIME = 0.2  # Minimum expected time for rate limiting test
NUM_TEST_REQUESTS = 3  # Number of requests for rate limiting test

# Expected keys in the result dictionary
EXPECTED_RESULT_KEYS = {"fitness", "metrics", "passed"}
EXPECTED_METRICS_KEYS = {"accuracy", "latency"}


@pytest.fixture
def mock_seal_provider():
    """Create a mock SEAL provider for testing."""
    mock = MagicMock(spec=SEALProvider)
    mock.submit_prompt = AsyncMock(return_value="dummy response")
    mock.parse_response = AsyncMock(
        return_value={
            "fitness": 0.9,
            "metrics": {"accuracy": 0.95, "latency": 0.1},
            "passed": True,
        }
    )
    return mock


@pytest.fixture
def seal_interface(mock_seal_provider):
    """Create a SEALInterface instance with a mock provider."""
    return SEALInterface(provider=mock_seal_provider)


@pytest.mark.asyncio
async def test_seal_interface_initialization(seal_interface):
    """Test that SEALInterface initializes correctly."""
    assert seal_interface is not None
    assert hasattr(seal_interface, "submit")
    assert hasattr(seal_interface, "provider")


@pytest.mark.asyncio
async def test_seal_interface_submit(seal_interface, mock_seal_provider):
    """Test program submission through SEAL interface."""
    test_prompt = "Test prompt"

    result = await seal_interface.submit(test_prompt)

    # Verify the result structure
    assert result is not None
    for key in EXPECTED_RESULT_KEYS:
        assert key in result, f"Expected key '{key}' not found in result"
    assert (
        result["fitness"] == TEST_FITNESS
    ), f"Expected fitness {TEST_FITNESS}, got {result['fitness']}"
    for key in EXPECTED_METRICS_KEYS:
        assert key in result["metrics"], f"Expected metric '{key}' not found"
    assert (
        result["metrics"]["accuracy"] == TEST_ACCURACY
    ), f"Expected accuracy {TEST_ACCURACY}, got {result['metrics']['accuracy']}"
    assert (
        result["metrics"]["latency"] == TEST_LATENCY
    ), f"Expected latency {TEST_LATENCY}, got {result['metrics']['latency']}"

    # Verify the provider methods were called
    mock_seal_provider.submit_prompt.assert_called_once_with(test_prompt)
    mock_seal_provider.parse_response.assert_called_once_with("dummy response")


@pytest.mark.asyncio
async def test_seal_interface_rate_limiting(seal_interface, mock_seal_provider):
    """Test that rate limiting works as expected."""
    # Set a high rate limit to test the delay
    seal_interface.rate_limit_per_sec = TEST_RATE_LIMIT

    # Record start time
    start_time = asyncio.get_event_loop().time()

    # Make multiple requests
    for _ in range(NUM_TEST_REQUESTS):
        await seal_interface.submit("test")

    # Verify minimum time has passed for the requests to complete
    elapsed = asyncio.get_event_loop().time() - start_time
    assert elapsed >= MIN_EXPECTED_TIME, (
        f"Expected at least {MIN_EXPECTED_TIME}s for {NUM_TEST_REQUESTS} requests, "
        f"but took {elapsed:.2f}s"
    )

    # Verify the correct number of calls
    assert mock_seal_provider.submit_prompt.call_count == NUM_TEST_REQUESTS


# Add more test cases for error conditions, edge cases, and specific SEAL features
