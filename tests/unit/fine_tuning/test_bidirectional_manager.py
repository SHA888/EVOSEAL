"""Tests for BidirectionalEvolutionManager.run_loop_cycle orchestration.

Verifies the new end-to-end loop method that wires training readiness
checking, training execution, and model deployment into a single cycle.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from evoseal.fine_tuning.bidirectional_manager import BidirectionalEvolutionManager


def _make_manager(tmp_path: Path) -> tuple[BidirectionalEvolutionManager, MagicMock]:
    """Build a BidirectionalEvolutionManager with mocked sub-components."""
    mock_dc = MagicMock()
    mock_tm = MagicMock()
    mock_tm.check_training_readiness = AsyncMock()
    mock_tm.run_training_cycle = AsyncMock()
    mock_tm.version_manager = MagicMock()
    mock_tm.version_manager.get_current_version = MagicMock()
    mock_tm.version_manager.deploy_version = AsyncMock()

    mgr = BidirectionalEvolutionManager(
        data_collector=mock_dc,
        training_manager=mock_tm,
        output_dir=tmp_path / "bim",
    )
    return mgr, mock_tm


# --- run_loop_cycle: skipped when not ready ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_skips_when_not_ready(tmp_path):
    """When training is not ready, the cycle must succeed with skipped=True."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.check_training_readiness.return_value = {
        "ready": False,
        "reason": "Insufficient samples",
    }

    result = await mgr.run_loop_cycle()

    assert result["success"] is True
    assert result["skipped"] is True
    assert "Insufficient" in result["reason"]
    assert "cycle_id" in result
    assert isinstance(result["cycle_id"], int)
    mock_tm.run_training_cycle.assert_not_awaited()
    # Stats: cycle recorded, but no training or improvement
    assert mgr.stats["total_evolution_cycles"] == 1
    assert mgr.stats["successful_training_cycles"] == 0
    assert mgr.stats["model_improvements"] == 0
    # State fields updated
    assert mgr.is_running is False
    assert mgr.last_check_time is not None
    assert len(mgr.evolution_history) == 1


# --- run_loop_cycle: training failure ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_training_failure(tmp_path):
    """When training fails, the cycle must return success=False with phase=training."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.check_training_readiness.return_value = {"ready": True}
    mock_tm.run_training_cycle.return_value = {
        "success": False,
        "error": "OOM during fine-tuning",
    }

    result = await mgr.run_loop_cycle()

    assert result["success"] is False
    assert result["phase"] == "training"
    assert "OOM" in result["error"]
    assert "cycle_id" in result
    assert mgr.stats["successful_training_cycles"] == 0
    assert mgr.stats["total_evolution_cycles"] == 1


# --- run_loop_cycle: training succeeds, validation passes, deploy succeeds ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_full_success(tmp_path):
    """Full cycle: train → validate → deploy → improvement recorded."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.check_training_readiness.return_value = {"ready": True}
    mock_tm.run_training_cycle.return_value = {
        "success": True,
        "validation_results": {"passed": True},
    }
    mock_tm.version_manager.get_current_version.return_value = {
        "version_id": "v1",
        "version_name": "model-v1",
    }
    mock_tm.version_manager.deploy_version.return_value = {
        "ollama_model": "model-v1",
        "version_id": "v1",
    }

    result = await mgr.run_loop_cycle()

    assert result["success"] is True
    assert result["phases"]["deploy"]["success"] is True
    assert "cycle_id" in result
    assert mgr.stats["successful_training_cycles"] == 1
    assert mgr.stats["model_improvements"] == 1
    assert mgr.stats["last_improvement"] is not None
    mock_tm.version_manager.deploy_version.assert_awaited_once_with("v1")


# --- run_loop_cycle: training succeeds, validation fails, deploy skipped ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_validation_fails_skips_deploy(tmp_path):
    """When validation doesn't pass, deploy must be skipped."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.check_training_readiness.return_value = {"ready": True}
    mock_tm.run_training_cycle.return_value = {
        "success": True,
        "validation_results": {"passed": False},
    }

    result = await mgr.run_loop_cycle()

    assert result["success"] is True
    assert result["phases"]["deploy"]["skipped"] is True
    assert mgr.stats["successful_training_cycles"] == 1
    assert mgr.stats["model_improvements"] == 0
    mock_tm.version_manager.deploy_version.assert_not_awaited()


# --- run_loop_cycle: deploy failure ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_deploy_failure(tmp_path):
    """Deploy failure must not count as an improvement but the cycle still succeeds."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.check_training_readiness.return_value = {"ready": True}
    mock_tm.run_training_cycle.return_value = {
        "success": True,
        "validation_results": {"passed": True},
    }
    mock_tm.version_manager.get_current_version.return_value = {
        "version_id": "v1",
    }
    mock_tm.version_manager.deploy_version.return_value = {
        "error": "ollama create failed",
    }

    result = await mgr.run_loop_cycle()

    assert result["success"] is True  # cycle itself succeeded
    assert result["phases"]["deploy"]["success"] is False
    assert mgr.stats["model_improvements"] == 0


# --- run_loop_cycle: exception handling ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_exception_handling(tmp_path):
    """An unexpected exception must be caught, not crash the caller."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.check_training_readiness.side_effect = RuntimeError("unexpected")

    result = await mgr.run_loop_cycle()

    assert result["success"] is False
    assert "unexpected" in result["error"]
    assert "cycle_id" in result
    assert mgr.is_running is False
    assert mgr.last_check_time is not None
    assert mgr.stats["total_evolution_cycles"] == 1


# --- run_loop_cycle: state fields are mutated ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_mutates_state_fields(tmp_path):
    """is_running, last_check_time, stats, and evolution_history must be updated."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.check_training_readiness.return_value = {"ready": False, "reason": "too few"}

    before = datetime.now()
    await mgr.run_loop_cycle()

    assert mgr.last_check_time >= before
    assert mgr.stats["total_evolution_cycles"] == 1
    assert len(mgr.evolution_history) == 1
    assert mgr.evolution_history[0]["results"]["skipped"] is True


# --- _deploy_trained_model: no current version ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deploy_trained_model_no_current_version(tmp_path):
    """When no version is registered, deploy must return an error."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.version_manager.get_current_version.return_value = None

    result = await mgr._deploy_trained_model({"success": True})

    assert result["success"] is False
    assert "no current version" in result["error"]


# --- run_loop_cycle: training result without validation_results key ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_missing_validation_results(tmp_path):
    """If training_result has no validation_results key, deploy must be skipped."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.check_training_readiness.return_value = {"ready": True}
    mock_tm.run_training_cycle.return_value = {"success": True}

    result = await mgr.run_loop_cycle()

    assert result["success"] is True
    assert result["phases"]["deploy"]["skipped"] is True
    assert mgr.stats["model_improvements"] == 0


# --- run_loop_cycle: re-entrancy guard ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_reentrancy_guard(tmp_path):
    """If is_running is already True, the cycle must return early without touching state."""
    mgr, mock_tm = _make_manager(tmp_path)
    mgr.is_running = True  # simulate a concurrent cycle

    result = await mgr.run_loop_cycle()

    assert result["success"] is False
    assert "already running" in result["error"]
    assert result["phases"] == {}
    # Must not have touched any sub-component
    mock_tm.check_training_readiness.assert_not_awaited()
    mock_tm.run_training_cycle.assert_not_awaited()
    # Stats and history must remain untouched
    assert mgr.stats["total_evolution_cycles"] == 0
    assert len(mgr.evolution_history) == 0


# --- run_loop_cycle: validation_results explicitly None ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_cycle_validation_results_none(tmp_path):
    """If validation_results is explicitly None, deploy must be skipped without error."""
    mgr, mock_tm = _make_manager(tmp_path)
    mock_tm.check_training_readiness.return_value = {"ready": True}
    mock_tm.run_training_cycle.return_value = {
        "success": True,
        "validation_results": None,
    }

    result = await mgr.run_loop_cycle()

    assert result["success"] is True
    assert result["phases"]["deploy"]["skipped"] is True
    assert mgr.stats["model_improvements"] == 0
    assert mgr.stats["successful_training_cycles"] == 1
