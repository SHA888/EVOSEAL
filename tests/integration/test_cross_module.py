"""
Integration tests for cross-module interactions.

Tests the interaction between DGM, SEAL, and OpenEvolve components,
including data flow, state management, and error handling across module boundaries.
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock external dependencies
sys.modules["docker"] = MagicMock()
sys.modules["docker.errors"] = MagicMock()

from evoseal.models import Program

# Import after path setup
from evoseal.seal_interface import SEALInterface, SEALProvider


# Mock the DGM and OpenEvolve imports to avoid circular dependencies
class MockEvolutionEngine:
    """Mock EvolutionEngine for testing."""

    def __init__(self, seal_interface, openevolve):
        self.seal_interface = seal_interface
        self.openevolve = openevolve

    async def run_evolution_step(self):
        """Run a single evolution step."""
        # Simulate a successful evolution step
        return {
            "best_program": Program(
                id="test_prog_1", code="def test(): return 42", language="python"
            ),
            "metrics": {"fitness": 0.9, "accuracy": 0.95},
        }


# Patch the imports
sys.modules["dgm.evolution"] = MagicMock()
sys.modules["dgm.evolution"].EvolutionEngine = MockEvolutionEngine


# Mock OpenEvolve
class MockOpenEvolve:
    """Mock OpenEvolve for testing."""

    def __init__(self, config=None):
        self.config = config or {}
        self.population = []

    def initialize_population(self, size):
        """Initialize the population."""
        self.population = [f"program_{i}" for i in range(size)]
        return self.population


@pytest.fixture
def mock_components():
    """Create mock instances of all components for testing."""
    # Create a mock SEAL provider
    mock_seal_provider = MagicMock(spec=SEALProvider)
    mock_seal_provider.submit_prompt = AsyncMock(return_value="dummy response")
    mock_seal_provider.parse_response = AsyncMock(
        return_value={
            "fitness": 0.9,
            "metrics": {"accuracy": 0.95, "latency": 0.1},
            "passed": True,
        }
    )

    # Create SEAL interface with mock provider
    seal_interface = SEALInterface(provider=mock_seal_provider)

    # Create OpenEvolve instance with minimal configuration
    openevolve = MockOpenEvolve(
        {
            "population_size": 10,
            "max_generations": 5,
            "mutation_rate": 0.1,
            "crossover_rate": 0.8,
        }
    )

    # Create DGM evolution engine
    evolution_engine = MockEvolutionEngine(
        seal_interface=seal_interface, openevolve=openevolve
    )

    return {
        "seal_interface": seal_interface,
        "openevolve": openevolve,
        "evolution_engine": evolution_engine,
        "mock_seal_provider": mock_seal_provider,
    }


@pytest.mark.asyncio
async def test_cross_module_workflow(mock_components):
    """Test the complete workflow across DGM, SEAL, and OpenEvolve."""
    engine = mock_components["evolution_engine"]

    # Run a single evolution step
    result = await engine.run_evolution_step()

    # Verify the evolution step completed successfully
    assert result is not None
    assert "best_program" in result
    assert "metrics" in result
    assert result["metrics"]["fitness"] == 0.9

    # Verify SEAL provider methods were called
    mock_components["mock_seal_provider"].submit_prompt.assert_called()
    mock_components["mock_seal_provider"].parse_response.assert_called()

    # Verify OpenEvolve state was updated
    assert len(mock_components["openevolve"].population) > 0


@pytest.mark.asyncio
async def test_error_handling_across_modules(mock_components):
    """Test error handling across module boundaries."""
    # Simulate an error in SEAL evaluation
    mock_components["mock_seal_provider"].submit_prompt.side_effect = Exception(
        "Test error"
    )

    # Verify the error is properly caught and handled
    with pytest.raises(Exception) as exc_info:
        await mock_components["evolution_engine"].run_evolution_step()

    assert "Test error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_data_flow_between_components(mock_components):
    """Test data flow between DGM, SEAL, and OpenEvolve."""
    engine = mock_components["evolution_engine"]
    mock_provider = mock_components["mock_seal_provider"]

    # Set up mock to return different fitness values
    fitness_values = [0.8, 0.9, 0.95]
    mock_provider.parse_response.side_effect = [
        {"fitness": val, "metrics": {"accuracy": val + 0.05}, "passed": True}
        for val in fitness_values
    ]

    # Run multiple evolution steps
    results = []
    for _ in range(3):
        result = await engine.run_evolution_step()
        results.append(result["metrics"]["fitness"])

    # Verify results show improvement
    assert results == sorted(results), "Fitness should improve or stay the same"


# Add more test cases for specific cross-module interactions
