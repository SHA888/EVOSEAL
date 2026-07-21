"""Tests for ContinuousEvolutionService._trigger_training_cycle.

Verifies the fix for the method-name bug: the service must call
run_training_cycle() (not the nonexistent start_training()) and must
check validation_results.passed (not validation_passed).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evoseal.services.continuous_evolution_service import ContinuousEvolutionService


def _make_service(tmp_path: Path) -> ContinuousEvolutionService:
    """Build a ContinuousEvolutionService with mocked internals."""
    with (
        patch("evoseal.services.continuous_evolution_service.EvolutionDataCollector"),
        patch("evoseal.services.continuous_evolution_service.BidirectionalEvolutionManager"),
    ):
        svc = ContinuousEvolutionService(data_dir=tmp_path / "svc")
    return svc


def test_trigger_training_calls_run_training_cycle(tmp_path):
    """_trigger_training_cycle must call run_training_cycle (not start_training)."""
    svc = _make_service(tmp_path)

    training_mgr = AsyncMock()
    training_mgr.get_training_status = AsyncMock(return_value={"ready_for_training": True})
    training_mgr.run_training_cycle = AsyncMock(
        return_value={"success": True, "validation_results": {"passed": True}}
    )

    svc.bidirectional_manager = MagicMock()
    svc.bidirectional_manager.training_manager = training_mgr

    asyncio.run(svc._trigger_training_cycle())

    # (1) run_training_cycle was awaited — proving we no longer call start_training
    training_mgr.run_training_cycle.assert_awaited_once()

    # (2) training_cycles_triggered incremented
    assert svc.service_stats["training_cycles_triggered"] == 1

    # (3) successful_improvements incremented because validation passed
    assert svc.service_stats["successful_improvements"] == 1


def test_trigger_training_validation_failed(tmp_path):
    """When validation_results.passed is False, successful_improvements stays 0."""
    svc = _make_service(tmp_path)

    training_mgr = AsyncMock()
    training_mgr.get_training_status = AsyncMock(return_value={"ready_for_training": True})
    training_mgr.run_training_cycle = AsyncMock(
        return_value={"success": True, "validation_results": {"passed": False}}
    )

    svc.bidirectional_manager = MagicMock()
    svc.bidirectional_manager.training_manager = training_mgr

    asyncio.run(svc._trigger_training_cycle())

    training_mgr.run_training_cycle.assert_awaited_once()
    assert svc.service_stats["training_cycles_triggered"] == 1
    assert svc.service_stats["successful_improvements"] == 0


# --- _run_evolution_cycle wiring tests ---


def _make_service_with_pipeline(tmp_path: Path) -> tuple:
    """Build a ContinuousEvolutionService with a mocked EvolutionPipeline."""
    mock_pipeline = AsyncMock()
    with (
        patch("evoseal.services.continuous_evolution_service.EvolutionDataCollector"),
        patch("evoseal.services.continuous_evolution_service.BidirectionalEvolutionManager"),
    ):
        svc = ContinuousEvolutionService(data_dir=tmp_path / "svc", pipeline=mock_pipeline)
    return svc, mock_pipeline


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_evolution_cycle_invokes_pipeline(tmp_path):
    """_run_evolution_cycle must call pipeline.run_evolution_cycle()."""
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)
    mock_pipeline.run_evolution_cycle.return_value = [
        {"iteration": 1, "success": True, "is_improvement": True}
    ]

    await svc._run_evolution_cycle()

    mock_pipeline.run_evolution_cycle.assert_awaited_once_with(iterations=1)
    assert svc.service_stats["evolution_cycles_completed"] == 1
    assert svc.service_stats["last_activity"] is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_evolution_cycle_handles_failure(tmp_path):
    """A failed pipeline iteration must still count as a completed cycle."""
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)
    mock_pipeline.run_evolution_cycle.return_value = [
        {"iteration": 1, "success": False, "error": "boom"}
    ]

    await svc._run_evolution_cycle()

    mock_pipeline.run_evolution_cycle.assert_awaited_once_with(iterations=1)
    assert svc.service_stats["evolution_cycles_completed"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_evolution_cycle_handles_pipeline_exception(tmp_path):
    """If the pipeline raises, the cycle must not crash the service."""
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)
    mock_pipeline.run_evolution_cycle.side_effect = RuntimeError("pipeline broke")

    # Should not raise
    await svc._run_evolution_cycle()

    mock_pipeline.run_evolution_cycle.assert_awaited_once_with(iterations=1)
    # Cycle counter must NOT increment on exception
    assert svc.service_stats["evolution_cycles_completed"] == 0


@pytest.mark.unit
def test_run_evolution_cycle_lazy_pipeline(tmp_path):
    """When no pipeline is injected, _get_pipeline creates one lazily."""
    with (
        patch("evoseal.services.continuous_evolution_service.EvolutionDataCollector"),
        patch("evoseal.services.continuous_evolution_service.BidirectionalEvolutionManager"),
    ):
        svc = ContinuousEvolutionService(data_dir=tmp_path / "svc")

    assert svc._pipeline is None

    mock_ep = AsyncMock()
    mock_ep.run_evolution_cycle.return_value = []
    with patch(
        "evoseal.services.continuous_evolution_service.EvolutionPipeline",
        return_value=mock_ep,
    ) as ep_cls:
        pipeline = svc._get_pipeline()
        ep_cls.assert_called_once()
        assert pipeline is mock_ep
        # Second call should reuse the same instance
        pipeline2 = svc._get_pipeline()
        assert pipeline2 is mock_ep
        ep_cls.assert_called_once()  # still only one call
