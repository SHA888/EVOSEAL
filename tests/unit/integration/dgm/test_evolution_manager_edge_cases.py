"""
Edge-case and error-handling tests for EvolutionManager, SEALInterface, and AgenticSystem.
"""

import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from integration.dgm.evolution_manager import EvolutionManager

# Patch all major external dependencies, including openevolve and submodules
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


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_empty_archive(temp_output_dir):
    with (
        patch("integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch("os.path.exists", return_value=True),
        patch("builtins.open", new_callable=MagicMock),
        patch("os.makedirs", return_value=None),
        patch("os.path.join", side_effect=lambda *args: "/".join(args)),
    ):
        mock_dgm.initialize_run.return_value = ([], 0)
        manager = EvolutionManager(temp_output_dir)
        assert manager.archive == []


def test_invalid_fitness_metrics(temp_output_dir):
    with (
        patch("integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch("os.path.exists", return_value=True),
        patch("builtins.open", new_callable=MagicMock),
        patch("os.makedirs", return_value=None),
        patch("os.path.join", side_effect=lambda *args: "/".join(args)),
    ):
        mock_dgm.initialize_run.return_value = (["run"], 0)
        mock_dgm.get_fitness_metrics.return_value = None
        manager = EvolutionManager(temp_output_dir)
        # Should raise or handle gracefully
        with pytest.raises(FileNotFoundError):
            manager.get_fitness_metrics("run")
