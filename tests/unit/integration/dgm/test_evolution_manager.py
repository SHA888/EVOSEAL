"""
Unit tests for EvolutionManager (integration.dgm.evolution_manager).
Covers initialization, archive management, mutation/crossover, and error handling.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from integration.dgm.data_adapter import DGMDataAdapter
from integration.dgm.evolution_manager import EvolutionManager

# Patch all external DGM dependencies and submodules for unit testing
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

EXPECTED_ARCHIVE_LEN = 2  # Expected length for test_get_archive
EXPECTED_GENERATION_AFTER_INCREMENT = 3  # For test_increment_generation


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_initialization(temp_output_dir):
    # Patch DGM_outer.initialize_run to avoid running real logic
    with patch("integration.dgm.evolution_manager.DGM_outer") as mock_dgm:
        mock_dgm.initialize_run.return_value = (["run1", "run2"], 0)
        manager = EvolutionManager(temp_output_dir)
        assert isinstance(manager.data_adapter, DGMDataAdapter)
        assert manager.archive == ["run1", "run2"]
        assert manager.current_generation == 0


def test_update_archive(temp_output_dir):
    with patch("integration.dgm.evolution_manager.DGM_outer") as mock_dgm:
        mock_dgm.initialize_run.return_value = (["runA"], 0)
        mock_dgm.update_archive.return_value = ["runA", "runB"]
        manager = EvolutionManager(temp_output_dir)
        updated = manager.update_archive(["runB"])
        assert updated == ["runA", "runB"]
        assert manager.archive == ["runA", "runB"]


def test_get_fitness_metrics_fallback(temp_output_dir):
    with (
        patch("integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch("integration.dgm.evolution_manager.os.path.exists", return_value=False),
    ):
        mock_dgm.initialize_run.return_value = (["runX"], 0)
        manager = EvolutionManager(temp_output_dir)
        # Should raise FileNotFoundError if neither model nor legacy JSON exists
        with pytest.raises(FileNotFoundError):
            manager.get_fitness_metrics("runX")


def test_increment_generation(temp_output_dir):
    with patch("integration.dgm.evolution_manager.DGM_outer") as mock_dgm:
        mock_dgm.initialize_run.return_value = (["run1"], 2)
        manager = EvolutionManager(temp_output_dir)
        manager.increment_generation()
        assert manager.current_generation == EXPECTED_GENERATION_AFTER_INCREMENT


def test_get_archive(temp_output_dir):
    with patch("integration.dgm.evolution_manager.DGM_outer") as mock_dgm:
        mock_dgm.initialize_run.return_value = (["id1", "id2"], 0)
        manager = EvolutionManager(temp_output_dir)
        archive = manager.get_archive()
        assert len(archive) == EXPECTED_ARCHIVE_LEN
        assert archive == ["id1", "id2"]
