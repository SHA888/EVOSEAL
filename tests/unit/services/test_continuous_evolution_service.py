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

from evoseal.evolution.data_collector import create_evolution_result
from evoseal.evolution.models import EvolutionStrategy
from evoseal.services.continuous_evolution_service import ContinuousEvolutionService


def _make_service(tmp_path: Path) -> ContinuousEvolutionService:
    """Build a ContinuousEvolutionService with mocked internals."""
    mock_dc = MagicMock()
    mock_dc.collect_result = AsyncMock()
    with (
        patch(
            "evoseal.services.continuous_evolution_service.EvolutionDataCollector",
            return_value=mock_dc,
        ),
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


def _make_service_with_pipeline(tmp_path: Path, evolution_iterations: int = 1) -> tuple:
    """Build a ContinuousEvolutionService with a mocked EvolutionPipeline."""
    mock_pipeline = AsyncMock()
    mock_dc = MagicMock()
    mock_dc.collect_result = AsyncMock()
    with (
        patch(
            "evoseal.services.continuous_evolution_service.EvolutionDataCollector",
            return_value=mock_dc,
        ),
        patch("evoseal.services.continuous_evolution_service.BidirectionalEvolutionManager"),
    ):
        svc = ContinuousEvolutionService(
            data_dir=tmp_path / "svc",
            pipeline=mock_pipeline,
            evolution_iterations=evolution_iterations,
        )
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
    assert svc.service_stats["evolution_cycle_errors"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_evolution_cycle_persists_only_successful_results(tmp_path):
    """Only successful pipeline results must be persisted via collect_result."""
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)
    mock_pipeline.run_evolution_cycle.return_value = [
        {
            "iteration": 1,
            "success": True,
            "is_improvement": True,
            "metrics": {"fitness": 0.9},
            "original_code": "x = 1",
            "improved_code": "x = 2",
        },
        {"iteration": 2, "success": False, "error": "nope"},
    ]

    await svc._run_evolution_cycle()

    # Only the successful result should be persisted
    assert svc.data_collector.collect_result.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_evolution_cycle_skips_codeless_results(tmp_path):
    """A successful result with no code diff must not be persisted.

    EvolutionPipeline doesn't return real code yet, so a codeless "success"
    would otherwise let training readiness fire on placeholder records with
    nothing to fine-tune on.
    """
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)
    mock_pipeline.run_evolution_cycle.return_value = [
        {"iteration": 1, "success": True, "is_improvement": True, "metrics": {"fitness": 0.9}},
    ]

    await svc._run_evolution_cycle()

    svc.data_collector.collect_result.assert_not_awaited()
    assert svc.service_stats["evolution_cycles_completed"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_evolution_cycle_skips_missing_fitness(tmp_path):
    """A successful result with no metrics.fitness must not be persisted.

    Defaulting to a synthetic fitness would inject fabricated training
    signal into the dataset.
    """
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)
    mock_pipeline.run_evolution_cycle.return_value = [
        {
            "iteration": 1,
            "success": True,
            "is_improvement": True,
            "original_code": "x = 1",
            "improved_code": "x = 2",
        },
    ]

    await svc._run_evolution_cycle()

    svc.data_collector.collect_result.assert_not_awaited()
    assert svc.service_stats["evolution_cycles_completed"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_evolution_cycle_persists_with_pipeline_strategy(tmp_path):
    """Persisted results must be tagged EvolutionStrategy.PIPELINE, not GA.

    EvolutionPipeline has no strategy selection of its own; tagging results
    as GENETIC_ALGORITHM would misattribute them in strategy_performance
    stats.
    """
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)
    mock_pipeline.run_evolution_cycle.return_value = [
        {
            "iteration": 1,
            "success": True,
            "is_improvement": True,
            "metrics": {"fitness": 0.9},
            "original_code": "x = 1",
            "improved_code": "x = 2",
        },
    ]

    await svc._run_evolution_cycle()

    persisted = svc.data_collector.collect_result.await_args.args[0]
    assert persisted.strategy == EvolutionStrategy.PIPELINE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_evolution_cycle_configurable_iterations(tmp_path):
    """evolution_iterations param must be forwarded to the pipeline."""
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path, evolution_iterations=3)
    mock_pipeline.run_evolution_cycle.return_value = []

    await svc._run_evolution_cycle()

    mock_pipeline.run_evolution_cycle.assert_awaited_once_with(iterations=3)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_evolution_cycle_rejects_non_list_result(tmp_path):
    """If the pipeline returns a non-list, the cycle must log and bail."""
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)
    mock_pipeline.run_evolution_cycle.return_value = "unexpected"

    # Must not raise
    await svc._run_evolution_cycle()

    # Cycle counter must NOT increment on bad shape
    assert svc.service_stats["evolution_cycles_completed"] == 0
    assert svc.service_stats["evolution_cycle_errors"] == 1


@pytest.mark.unit
def test_run_evolution_cycle_lazy_pipeline(tmp_path):
    """When no pipeline is injected, _get_pipeline creates one lazily."""
    mock_dc = MagicMock()
    mock_dc.collect_result = AsyncMock()
    with (
        patch(
            "evoseal.services.continuous_evolution_service.EvolutionDataCollector",
            return_value=mock_dc,
        ),
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
        # Config must be passed through (not a bare constructor)
        call_kwargs = ep_cls.call_args
        assert "config" in call_kwargs.kwargs
        assert pipeline is mock_ep
        # Second call should reuse the same instance
        pipeline2 = svc._get_pipeline()
        assert pipeline2 is mock_ep
        ep_cls.assert_called_once()  # still only one call


# --- _check_training_readiness key-path tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_training_readiness_uses_successful_count(tmp_path):
    """_check_training_readiness must read collection_stats.successful_count.

    The get_statistics() key path is: ["collection_stats"]["successful_count"].
    If this path is wrong, total_results silently stays 0 and training never
    triggers — a silent failure mode.  This test asserts the key path matches
    the real shape returned by EvolutionDataCollector.get_statistics().
    """
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)

    # Simulate a real get_statistics() return shape
    svc.data_collector.get_statistics = MagicMock(
        return_value={
            "collection_stats": {
                "total_collected": 10,
                "successful_count": 7,
                "failed_count": 3,
            },
            "strategy_performance": {},
            "improvement_patterns": {},
            "memory_usage": {},
        }
    )

    # Patch _trigger_training_cycle so we don't actually run training
    svc._trigger_training_cycle = AsyncMock()

    # With min_evolution_samples=5, 7 successful results should trigger
    svc.min_evolution_samples = 5
    await svc._check_training_readiness()
    svc._trigger_training_cycle.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_training_readiness_below_threshold(tmp_path):
    """Training must NOT trigger when successful_count < min_evolution_samples."""
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)

    svc.data_collector.get_statistics = MagicMock(
        return_value={
            "collection_stats": {
                "total_collected": 10,
                "successful_count": 3,
                "failed_count": 7,
            },
            "strategy_performance": {},
            "improvement_patterns": {},
            "memory_usage": {},
        }
    )

    svc._trigger_training_cycle = AsyncMock()
    svc.min_evolution_samples = 5

    await svc._check_training_readiness()
    svc._trigger_training_cycle.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_training_readiness_with_real_collector(tmp_path):
    """Integration: key path must work with the real EvolutionDataCollector."""
    svc, mock_pipeline = _make_service_with_pipeline(tmp_path)

    # Use a real data_collector (not mocked) to verify the key path
    from evoseal.evolution.data_collector import EvolutionDataCollector
    from evoseal.evolution.models import EvolutionResult

    real_dc = EvolutionDataCollector(data_dir=tmp_path / "real_dc")
    svc.data_collector = real_dc
    svc._trigger_training_cycle = AsyncMock()
    svc.min_evolution_samples = 2

    # Add two successful results to cross the threshold
    for _ in range(2):
        result = create_evolution_result(
            original_code="x = 1",
            improved_code="x = 2",
            fitness_score=0.9,
            strategy=EvolutionStrategy.GENETIC_ALGORITHM,
        )
        await real_dc.collect_result(result)

    await svc._check_training_readiness()
    svc._trigger_training_cycle.assert_awaited_once()
