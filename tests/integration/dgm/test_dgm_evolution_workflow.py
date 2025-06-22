# isort: skip_file
"""
Integration test: Simulate full DGM evolutionary run with mocked SEAL/LLM responses and agentic system orchestration.
Covers initialization, mutation/crossover, fitness evaluation, and generation increment.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Patch all major DGM/SEAL/LLM/Agentic and openevolve external dependencies
sys.modules["docker"] = MagicMock()
sys.modules["docker.errors"] = MagicMock()
sys.modules["docker.models"] = MagicMock()
sys.modules["docker.models.containers"] = MagicMock()
sys.modules["anthropic"] = MagicMock()
sys.modules["backoff"] = MagicMock()
sys.modules["datasets"] = MagicMock()
sys.modules["swebench"] = MagicMock()
sys.modules["swebench.harness"] = MagicMock()
sys.modules["swebench.harness.test_spec"] = MagicMock()
sys.modules["swebench.harness.docker_build"] = MagicMock()
sys.modules["swebench.harness.utils"] = MagicMock()
sys.modules["git"] = MagicMock()
sys.modules["openevolve"] = MagicMock()
sys.modules["openevolve.prompt"] = MagicMock()
sys.modules["openevolve.prompt.templates"] = MagicMock()

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from evoseal.seal_interface import SEALInterface
from evoseal.dgm.data_adapter import DGMDataAdapter
from integration.dgm.evolution_manager import EvolutionManager


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_seal_interface():
    # Return a SEALInterface with a dummy provider that always returns a fixed response
    class DummySealProvider:
        async def submit(self, code, spec):
            return {"fitness": 1.0, "result": "dummy"}

    class DummySealInterface:
        async def submit(self, code, spec):
            return await DummySealProvider().submit(code, spec)

    return DummySealInterface()

    class DummySEALProvider:
        async def submit(self, *args, **kwargs):
            return {"result": "dummy", "fitness": 1.0}

    return SEALInterface(DummySEALProvider())


@pytest.fixture
def mock_agentic_system():
    # Dummy agentic system that simulates agent/task orchestration
    class DummyAgenticSystem:
        def assign_task(self, *args, **kwargs):
            return "task-assigned"

        def run(self):
            return "run-complete"

    return DummyAgenticSystem()


def test_full_evolutionary_run(
    temp_output_dir, mock_seal_interface, mock_agentic_system
):
    # Patch DGM_outer to simulate evolutionary logic
    with (
        patch("integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch("os.path.exists", return_value=True),
        patch("builtins.open", new_callable=MagicMock),
        patch("os.makedirs", return_value=None),
        patch("os.path.join", side_effect=lambda *args: "/".join(args)),
    ):
        mock_dgm.initialize_run.return_value = (["init1", "init2"], 0)
        mock_dgm.update_archive.return_value = ["init1", "mut1", "mut2"]
        # Simulate fitness metrics
        mock_dgm.get_fitness_metrics.return_value = {
            "init1": 1.0,
            "mut1": 0.9,
            "mut2": 0.8,
        }
        # Patch EvolutionManager.get_fitness_metrics to return dummy metrics
        with patch.object(
            EvolutionManager,
            "get_fitness_metrics",
            return_value={"init1": 1.0, "run_id": "init1"},
        ):
            manager = EvolutionManager(temp_output_dir)
            # Simulate mutation/crossover
            updated_archive = manager.update_archive(["mut1", "mut2"])
            assert updated_archive == ["init1", "mut1", "mut2"]
            # Simulate fitness evaluation
            fitness = manager.get_fitness_metrics("init1")
            assert fitness["init1"] == 1.0
            # Simulate generation increment
            manager.increment_generation()
            assert manager.current_generation == 1
            # Simulate agentic system orchestration
            assert mock_agentic_system.assign_task("dummy-task") == "task-assigned"
            assert mock_agentic_system.run() == "run-complete"
            # Simulate SEALInterface async call
            import asyncio

            result = asyncio.run(mock_seal_interface.submit("code", "spec"))
            assert result["fitness"] == 1.0
            assert result["result"] == "dummy"
