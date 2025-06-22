"""
Pytest configuration and fixtures for integration tests.
"""

from __future__ import annotations

import asyncio
import shutil

# Add the project root to the Python path
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mock external dependencies
sys.modules["docker"] = MagicMock()
sys.modules["docker.errors"] = MagicMock()
sys.modules["openevolve"] = MagicMock()

# Import after path setup
from evoseal.integration.seal.seal_interface import SEALInterface
from evoseal.models import Program
from evoseal.providers.seal_providers import SEALProvider

# Re-export for convenience
pytest_plugins = ["pytest_asyncio"]


# Define SEALProvider protocol for type checking
class SEALProviderProtocol:
    """Protocol for SEAL providers."""

    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str: ...
    async def parse_response(self, response: str) -> dict[str, Any]: ...


@pytest.fixture(scope="function")
def temp_project_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project directory for testing.

    Args:
        tmp_path: Pytest fixture providing a temporary directory

    Yields:
        Path to the temporary project directory
    """
    # Create a test project structure
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create source directory
    src_dir = project_dir / "src"
    src_dir.mkdir()

    # Create output directory
    output_dir = project_dir / "output"
    output_dir.mkdir()

    # Create config directory
    config_dir = project_dir / ".evoseal"
    config_dir.mkdir()

    yield project_dir

    # Cleanup (handled by pytest's tmp_path fixture)
    shutil.rmtree(project_dir, ignore_errors=True)


@pytest.fixture
def mock_seal_provider():
    """Create a mock SEAL provider with realistic responses."""
    # Create a mock that will be awaitable
    mock = AsyncMock()

    # Configure the mock to return a coroutine
    mock.submit_prompt.return_value = "dummy response"
    mock.parse_response.return_value = {
        "fitness": 0.9,
        "metrics": {"accuracy": 0.95, "latency": 0.1},
        "passed": True,
    }

    return mock


@pytest.fixture
def seal_interface(mock_seal_provider: MagicMock) -> SEALInterface:
    """Create a SEALInterface instance with a mock provider."""
    return SEALInterface(provider=mock_seal_provider)


@pytest.fixture
def sample_program() -> Program:
    """Create a sample program for testing."""
    return Program(id="test_prog_1", code="def test(): return 42", language="python")


@pytest.fixture
def sample_program_list(sample_program: Program) -> list[Program]:
    """Create a list of sample programs for testing."""
    return [
        sample_program,
        Program(id="test_prog_2", code="def test(): return 43", language="python"),
    ]


@pytest.fixture
def evolution_config() -> dict[str, Any]:
    """Return a basic configuration for evolution testing."""
    return {
        "population_size": 10,
        "max_generations": 5,
        "mutation_rate": 0.1,
        "crossover_rate": 0.8,
    }


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_evolution_engine():
    """Create a mock evolution engine for testing."""

    class MockEvolutionEngine:
        def __init__(self, *args, **kwargs):
            self.population = []
            self.generation = 0

        async def run_evolution_step(self):
            self.generation += 1
            return {
                "best_program": Program(
                    id=f"best_gen_{self.generation}",
                    code=f"def gen_{self.generation}(): return {self.generation}",
                    language="python",
                ),
                "metrics": {"fitness": 0.8 + (self.generation * 0.05)},
            }

    return MockEvolutionEngine()


@pytest.fixture
def mock_controller():
    """Create a mock Controller instance for testing."""

    class MockController:
        def __init__(self, config=None):
            self.config = config or {}
            self.population = []

        def initialize_population(self, size):
            self.population = [f"program_{i}" for i in range(size)]
            return self.population

    return MockController()


@pytest.fixture(scope="function")
def sample_config() -> dict:
    """Return a sample configuration for testing."""
    return {
        "population_size": 10,
        "max_generations": 100,
        "mutation_rate": 0.1,
        "crossover_rate": 0.8,
        "elitism": 1,
        "selection": "tournament",
        "tournament_size": 3,
    }
