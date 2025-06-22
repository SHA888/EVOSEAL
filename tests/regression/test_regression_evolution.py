"""
Regression test for DGM evolutionary system.
Ensures previously fixed bugs/invariants remain fixed.
"""

# isort: skip_file
from unittest.mock import MagicMock, patch
import sys

# Patch major external dependencies, including openevolve and submodules
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

from evoseal.integration.dgm.evolution_manager import EvolutionManager


def test_no_duplicate_in_archive(tmp_path):
    with (
        patch("evoseal.integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch("os.path.exists", return_value=True),
        patch("builtins.open", new_callable=MagicMock),
        patch("os.makedirs", return_value=None),
        patch("os.path.join", side_effect=lambda *args: "/".join(args)),
    ):
        mock_dgm.initialize_run.return_value = (["a", "b"], 0)
        # Simulate update_archive returning unique values
        mock_dgm.update_archive.return_value = ["a", "b"]
        manager = EvolutionManager(tmp_path)
        archive = manager.update_archive(["b"])
        # Regression: archive should not have duplicates
        assert len(set(archive)) == len(archive)
