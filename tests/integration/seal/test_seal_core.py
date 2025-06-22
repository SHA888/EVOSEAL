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
from evoseal.seal_interface import SEALInterface, SEALProvider


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
    assert "fitness" in result
    assert result["fitness"] == 0.9
    assert result["metrics"]["accuracy"] == 0.95

    # Verify the provider methods were called
    mock_seal_provider.submit_prompt.assert_called_once_with(test_prompt)
    mock_seal_provider.parse_response.assert_called_once_with("dummy response")


@pytest.mark.asyncio
async def test_seal_interface_rate_limiting(seal_interface, mock_seal_provider):
    """Test that rate limiting works as expected."""
    # Set a high rate limit to test the delay
    seal_interface.rate_limit_per_sec = 10  # 10 requests per second max

    # Record start time
    start_time = asyncio.get_event_loop().time()

    # Make multiple requests
    for _ in range(3):
        await seal_interface.submit("test")

    # Verify at least 0.2 seconds have passed (3 requests at 10/s should take ~0.2s)
    elapsed = asyncio.get_event_loop().time() - start_time
    assert elapsed >= 0.2

    # Verify the correct number of calls
    assert mock_seal_provider.submit_prompt.call_count == 3


# Add more test cases for error conditions, edge cases, and specific SEAL features
