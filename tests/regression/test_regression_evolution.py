"""
Regression test for DGM evolutionary system.
Ensures previously fixed bugs/invariants remain fixed.
"""

# isort: skip_file
from unittest.mock import MagicMock, patch
import sys

# Major external dependencies that evolution_manager imports but that we do not
# want to require (or actually execute) for this regression test.
_MOCKED_MODULES = (
    "docker",
    "docker.errors",
    "docker.models",
    "docker.models.containers",
    "anthropic",
    "backoff",
    "datasets",
    "swebench",
    "swebench.harness",
    "swebench.harness.test_spec",
    "swebench.harness.docker_build",
    "swebench.harness.utils",
    "git",
    "openevolve",
    "openevolve.prompt",
    "openevolve.prompt.templates",
)

# Install the mocks ONLY for the duration of the import below, then restore.
# pytest-xdist workers import every test module during collection, so leaving
# these in sys.modules would poison unrelated tests in the same process -- e.g.
# a mocked `git` makes the shared `test_repo` fixture's Repo.init a no-op.
_saved_modules = {name: sys.modules.get(name) for name in _MOCKED_MODULES}
for _name in _MOCKED_MODULES:
    sys.modules[_name] = MagicMock()
try:
    from evoseal.integration.dgm.evolution_manager import EvolutionManager
finally:
    for _name, _module in _saved_modules.items():
        if _module is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _module


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
