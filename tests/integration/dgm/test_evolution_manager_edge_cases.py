# ruff: noqa: E402
# isort: skip_file
"""
Edge-case and error-handling tests for EvolutionManager, SEALInterface, and AgenticSystem.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

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

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
)

import pytest

from evoseal.integration.dgm.evolution_manager import EvolutionManager


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_empty_archive(temp_output_dir):
    with (
        patch("evoseal.integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
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
        patch("evoseal.integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch("os.path.exists", return_value=False),
    ):
        mock_dgm.initialize_run.return_value = (["run1"], 0)
        manager = EvolutionManager(temp_output_dir)

        # Should raise FileNotFoundError when metadata file doesn't exist
        with pytest.raises(FileNotFoundError):
            manager.get_fitness_metrics("run1")


def test_dgm_outer_raises_on_init(temp_output_dir):
    with patch("evoseal.integration.dgm.evolution_manager.DGM_outer") as mock_dgm:
        # Make initialize_run raise an exception
        mock_dgm.initialize_run.side_effect = RuntimeError("DGM initialization failed")

        # The actual error message should match what's raised by the code
        with pytest.raises(RuntimeError, match="DGM initialization failed"):
            EvolutionManager(temp_output_dir)


def test_malformed_legacy_metadata_json(temp_output_dir):
    import pydantic_core

    with (
        patch("evoseal.integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch("os.path.exists", return_value=True),
        patch("builtins.open", new_callable=MagicMock) as mock_open,
        patch("os.makedirs", return_value=None),
        patch("os.path.join", side_effect=lambda *args: "/".join(args)),
    ):
        mock_dgm.initialize_run.return_value = (["run"], 0)
        mock_open.return_value.__enter__.return_value.read.return_value = "not json"
        manager = EvolutionManager(temp_output_dir)
        # Should raise a ValidationError from Pydantic when parsing invalid JSON
        with pytest.raises(pydantic_core._pydantic_core.ValidationError):
            manager.get_fitness_metrics("run")


def test_data_adapter_returns_none(temp_output_dir):
    with (
        patch("evoseal.integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch(
            "evoseal.integration.dgm.evolution_manager.DGMDataAdapter.load_evaluation_result",
            return_value=None,
        ),
        patch("os.path.exists", return_value=False),
        patch("os.makedirs", return_value=None),
        patch("os.path.join", side_effect=lambda *args: "/".join(args)),
    ):
        mock_dgm.initialize_run.return_value = (["run"], 0)
        manager = EvolutionManager(temp_output_dir)
        with pytest.raises(FileNotFoundError):
            manager.get_fitness_metrics("run")


def test_corrupted_archive_entries(temp_output_dir):
    with patch("evoseal.integration.dgm.evolution_manager.DGM_outer") as mock_dgm:
        mock_dgm.initialize_run.return_value = (["run1", None, "run2", ""], 0)
        manager = EvolutionManager(temp_output_dir)
        # Archive currently preserves all entries as-is (including None/empty)
        # Document this behavior and assert the actual content
        assert manager.archive == ["run1", None, "run2", ""]
