"""
Benchmark script for DGM evolutionary system (mocked dependencies).
Measures time per evolutionary cycle. Run with: pytest benchmarks/benchmark_evolution.py
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from integration.dgm.evolution_manager import EvolutionManager

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

MAX_BENCHMARK_SECONDS = 5


def test_benchmark_evolution_cycle(tmp_path: Path) -> None:
    with (
        patch("integration.dgm.evolution_manager.DGM_outer") as mock_dgm,
        patch("os.path.exists", return_value=True),
        patch("os.makedirs", return_value=None),
        patch("builtins.open", new_callable=MagicMock),
        patch("os.path.join", side_effect=lambda *args: "/".join(args)),
    ):
        mock_dgm.initialize_run.return_value = (["init1", "init2"], 0)
        mock_dgm.update_archive.return_value = ["init1", "mut1", "mut2"]
        start = time.time()
        manager = EvolutionManager(str(tmp_path))
        for _ in range(10):
            manager.update_archive([f"mut{_}"])
            manager.increment_generation()
        elapsed = time.time() - start
        print(f"10 evolutionary cycles took {elapsed:.4f} seconds")
        assert elapsed < MAX_BENCHMARK_SECONDS  # Should be fast with mocks
