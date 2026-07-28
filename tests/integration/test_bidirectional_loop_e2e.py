"""End-to-end integration test for the bidirectional evolution loop.

Exercises the full cycle: collect → train → validate → deploy → regenerate.

Unlike the unit tests in ``test_bidirectional_manager.py`` (which mock
``TrainingManager`` entirely), this test wires real component instances
together and mocks only the true external boundaries (GPU fine-tuning,
Ollama validation/deploy):

- ``EvolutionDataCollector``: real, file-backed (tmp_path)
- ``ModelVersionManager``: real, file-backed (tmp_path)
- ``TrainingManager``: real orchestration, including the real
  ``check_training_readiness()`` and ``prepare_training_data()`` (which in
  turn drives a real ``TrainingDataBuilder``); only ``fine_tuner`` and
  ``validator`` are mocked
- ``BidirectionalEvolutionManager``: real, exercising ``run_loop_cycle()``
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip(
    "datasets", reason="Bidirectional loop tests require 'datasets' for HuggingFace format"
)

from evoseal.evolution import EvolutionDataCollector
from evoseal.evolution.data_collector import create_evolution_result
from evoseal.fine_tuning.bidirectional_manager import BidirectionalEvolutionManager
from evoseal.fine_tuning.training_manager import TrainingManager
from evoseal.fine_tuning.version_manager import ModelVersionManager

pytestmark = [pytest.mark.integration]


async def _seed_data_collector(dc: EvolutionDataCollector, count: int = 150) -> None:
    """Populate *dc* with results realistic enough to clear the real pipeline.

    The synthetic code is deliberately shaped to satisfy
    ``TrainingDataBuilder``'s quality filters (minimum code length, valid
    syntax, and a genuine improvement marker — here, added error handling
    and a docstring) so that ``TrainingManager.prepare_training_data()`` can
    run for real instead of being mocked at that boundary.

    Uses the real ``collect_result`` API so that pattern tracking, callbacks,
    and persistence are all exercised.  Callers must ``await`` this.
    """
    for i in range(count):
        original_code = f"def func_{i}(x):\n    y = x + 1\n    z = y * 2\n    return z\n"
        improved_code = (
            f"def func_{i}(x):\n"
            f'    """Compute the transformed value for x."""\n'
            f"    try:\n"
            f"        y = x + 1\n"
            f"        z = y * 2\n"
            f"        return z\n"
            f"    except TypeError:\n"
            f"        return None\n"
        )
        result = create_evolution_result(
            original_code=original_code,
            improved_code=improved_code,
            fitness_score=0.85,
            task_description=f"task-{i}",
        )
        await dc.collect_result(result)


async def _make_data_collector(tmp_path: Path) -> EvolutionDataCollector:
    """Create and seed an ``EvolutionDataCollector`` backed by *tmp_path*."""
    dc = EvolutionDataCollector(data_dir=tmp_path / "evolution_data")
    await _seed_data_collector(dc)
    return dc


# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_bidirectional_loop_cycle(tmp_path):
    """Full cycle: readiness → train → validate → deploy → stats updated."""
    # --- real components ---
    dc = await _make_data_collector(tmp_path)
    version_mgr = ModelVersionManager(versions_dir=tmp_path / "versions")

    training_mgr = TrainingManager(
        data_collector=dc,
        version_manager=version_mgr,
        output_dir=tmp_path / "training",
        min_training_samples=100,
    )

    bim = BidirectionalEvolutionManager(
        data_collector=dc,
        training_manager=training_mgr,
        output_dir=tmp_path / "bim",
        min_evolution_cycles=1,
    )

    # --- mock external boundaries ---

    # fine_tune_model: return success (no GPU needed).
    fine_tune_result = {
        "success": True,
        "model_save_path": str(tmp_path / "models" / "checkpoint-final"),
        "train_loss": 0.35,
        "training_examples_count": 50,
        "fallback_mode": True,
    }

    # validate_model: return passing validation (no Ollama needed).
    validation_result = {
        "overall_score": 0.82,
        "passed": True,
        "test_results": {},
        "recommendations": [],
    }

    # deploy_version: return success (no Ollama subprocess needed).
    deploy_result = {
        "ollama_model": "test-model-v1",
        "version_id": "v-test-1",
    }

    # --- apply mocks and run ---
    with (
        patch.object(
            training_mgr.fine_tuner,
            "fine_tune_model",
            new_callable=AsyncMock,
            return_value=fine_tune_result,
        ),
        patch.object(
            training_mgr.validator,
            "validate_model",
            new_callable=AsyncMock,
            return_value=validation_result,
        ),
        patch.object(
            version_mgr, "deploy_version", new_callable=AsyncMock, return_value=deploy_result
        ),
    ):
        result = await bim.run_loop_cycle()

    # --- assertions: cycle succeeded ---
    assert result["success"] is True
    assert result.get("skipped") is not True
    assert "cycle_id" in result

    # Phases were all executed.
    phases = result["phases"]
    assert "readiness" in phases
    assert phases["readiness"]["ready"] is True
    assert "training" in phases
    assert phases["training"]["success"] is True
    assert phases["training"]["data_prep_results"]["success"] is True
    assert phases["training"]["data_prep_results"]["examples_count"] > 0
    assert "deploy" in phases
    assert phases["deploy"]["success"] is True

    # Version was registered.
    assert version_mgr.registry["current_version"] is not None
    assert len(version_mgr.registry["versions"]) == 1

    # Stats updated correctly.
    assert bim.stats["total_evolution_cycles"] == 1
    assert bim.stats["successful_training_cycles"] == 1
    assert bim.stats["model_improvements"] == 1
    assert bim.stats["last_improvement"] is not None

    # State fields updated.
    assert bim.is_running is False
    assert bim.last_check_time is not None
    assert len(bim.evolution_history) == 1


@pytest.mark.asyncio
async def test_readiness_skip_records_cycle(tmp_path):
    """When readiness fails the cycle is recorded as skipped, not errored."""
    dc = await _make_data_collector(tmp_path)

    # Override min_training_samples to be very high so readiness fails
    # against the real (150) seeded candidate count.
    training_mgr = TrainingManager(
        data_collector=dc,
        output_dir=tmp_path / "training",
        min_training_samples=9999,
    )

    bim = BidirectionalEvolutionManager(
        data_collector=dc,
        training_manager=training_mgr,
        output_dir=tmp_path / "bim",
    )

    result = await bim.run_loop_cycle()

    assert result["success"] is True
    assert result["skipped"] is True
    assert "Insufficient" in result.get("reason", "")
    assert "cycle_id" in result

    # Stats: cycle counted, but no training or improvement.
    assert bim.stats["total_evolution_cycles"] == 1
    assert bim.stats["successful_training_cycles"] == 0
    assert bim.stats["model_improvements"] == 0
    assert len(bim.evolution_history) == 1


@pytest.mark.asyncio
async def test_training_failure_propagates(tmp_path):
    """A training failure must surface as success=False with phase=training."""
    dc = await _make_data_collector(tmp_path)
    version_mgr = ModelVersionManager(versions_dir=tmp_path / "versions")

    training_mgr = TrainingManager(
        data_collector=dc,
        version_manager=version_mgr,
        output_dir=tmp_path / "training",
        min_training_samples=100,
    )

    bim = BidirectionalEvolutionManager(
        data_collector=dc,
        training_manager=training_mgr,
        output_dir=tmp_path / "bim",
    )

    with patch.object(
        training_mgr.fine_tuner,
        "fine_tune_model",
        new_callable=AsyncMock,
        return_value={"success": False, "error": "OOM during fine-tuning"},
    ):
        result = await bim.run_loop_cycle()

    assert result["success"] is False
    assert result["phase"] == "training"
    assert "OOM" in result["error"]

    # No training success or improvement counted.
    assert bim.stats["successful_training_cycles"] == 0
    assert bim.stats["model_improvements"] == 0
    # But the cycle itself was recorded.
    assert bim.stats["total_evolution_cycles"] == 1
    assert len(bim.evolution_history) == 1


@pytest.mark.asyncio
async def test_validation_failure_skips_deploy(tmp_path):
    """When validation fails, deploy must be skipped and improvement not counted."""
    dc = await _make_data_collector(tmp_path)
    version_mgr = ModelVersionManager(versions_dir=tmp_path / "versions")

    training_mgr = TrainingManager(
        data_collector=dc,
        version_manager=version_mgr,
        output_dir=tmp_path / "training",
        min_training_samples=100,
    )

    bim = BidirectionalEvolutionManager(
        data_collector=dc,
        training_manager=training_mgr,
        output_dir=tmp_path / "bim",
    )

    with (
        patch.object(
            training_mgr.fine_tuner,
            "fine_tune_model",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "model_save_path": str(tmp_path / "models" / "checkpoint-final"),
                "train_loss": 0.35,
                "training_examples_count": 50,
            },
        ),
        patch.object(
            training_mgr.validator,
            "validate_model",
            new_callable=AsyncMock,
            return_value={"overall_score": 0.4, "passed": False, "test_results": {}},
        ),
    ):
        result = await bim.run_loop_cycle()

    assert result["success"] is True
    assert result["phases"]["deploy"]["skipped"] is True
    assert bim.stats["successful_training_cycles"] == 1
    assert bim.stats["model_improvements"] == 0


@pytest.mark.asyncio
async def test_two_sequential_cycles(tmp_path):
    """Two consecutive loop cycles must accumulate stats and history correctly."""
    dc = await _make_data_collector(tmp_path)
    version_mgr = ModelVersionManager(versions_dir=tmp_path / "versions")

    training_mgr = TrainingManager(
        data_collector=dc,
        version_manager=version_mgr,
        output_dir=tmp_path / "training",
        min_training_samples=100,
    )

    bim = BidirectionalEvolutionManager(
        data_collector=dc,
        training_manager=training_mgr,
        output_dir=tmp_path / "bim",
        min_evolution_cycles=1,
    )

    with (
        patch.object(
            training_mgr.fine_tuner,
            "fine_tune_model",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "model_save_path": str(tmp_path / "models" / "checkpoint"),
                "train_loss": 0.3,
                "training_examples_count": 50,
            },
        ),
        patch.object(
            training_mgr.validator,
            "validate_model",
            new_callable=AsyncMock,
            return_value={"overall_score": 0.85, "passed": True, "test_results": {}},
        ),
        patch.object(
            version_mgr,
            "deploy_version",
            new_callable=AsyncMock,
            return_value={"ollama_model": "test-model", "version_id": "v-1"},
        ),
    ):
        r1 = await bim.run_loop_cycle()

        # Reset the 1-hour minimum-interval guard so the second cycle isn't
        # rejected by check_training_readiness.  ``last_training_time`` is a
        # public attribute (documented in ``get_training_status``); there is
        # no ``force=True`` API on the readiness check, so clearing it
        # directly is the simplest correct approach.
        training_mgr.last_training_time = None

        r2 = await bim.run_loop_cycle()

    assert r1["success"] is True
    assert r2["success"] is True

    # Stats accumulate across cycles.
    assert bim.stats["total_evolution_cycles"] == 2
    assert bim.stats["successful_training_cycles"] == 2
    assert bim.stats["model_improvements"] == 2
    assert len(bim.evolution_history) == 2

    # Each cycle got its own cycle_id.
    assert r1["cycle_id"] != r2["cycle_id"]
    assert r1["cycle_id"] == 0
    assert r2["cycle_id"] == 1

    # Registry has two distinct versions (no overwrite/collision).
    assert len(version_mgr.registry["versions"]) == 2
    v_ids = [v["version_id"] for v in version_mgr.registry["versions"]]
    assert v_ids[0] != v_ids[1]
