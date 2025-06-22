"""
Benchmark for the DGM evolutionary loop using pytest-benchmark.
Run with: pytest benchmarks/test_evolution_benchmark.py --benchmark-only
"""

import os
import sys
import time
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evoseal.integration.dgm.evolution_manager import EvolutionManager

# Ensure project root is in sys.path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Patch all major external dependencies before any imports
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


def temp_output_dir() -> Generator[str, None, None]:
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_evolution_benchmark(temp_output_dir: str) -> None:
    with (
        patch("evoseal.integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch("os.path.exists", return_value=True),
        patch("os.makedirs", return_value=None),
        patch("builtins.open", new_callable=MagicMock),
        patch("os.path.join", side_effect=lambda *args: "/".join(args)),
    ):
        mock_dgm.initialize_run.return_value = (["init1", "init2"], 0)
        mock_dgm.update_archive.return_value = ["init1", "mut1", "mut2"]

        def run_cycles() -> None:
            manager = EvolutionManager(temp_output_dir)
            for _ in range(10):
                manager.update_archive([f"mut{_}"])
                manager.increment_generation()

        pytest.benchmark(run_cycles)
