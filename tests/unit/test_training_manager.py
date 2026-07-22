"""Regression tests for TrainingManager readiness-check ordering bug.

Bug: run_training_cycle() set self.current_training BEFORE calling
check_training_readiness(). Since the readiness check treats any non-None
current_training as "already in progress", every call was rejected.

Fix: check_training_readiness() is now called BEFORE setting
self.current_training.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from evoseal.fine_tuning.training_manager import TrainingManager


def _make_manager(min_samples: int = 10) -> TrainingManager:
    """Build a TrainingManager with a mock data_collector that reports enough samples."""
    collector = MagicMock()
    collector.get_statistics.return_value = {"training_candidates": min_samples + 5}
    return TrainingManager(data_collector=collector, min_training_samples=min_samples)


@pytest.mark.asyncio
async def test_run_training_cycle_passes_readiness_gate():
    """run_training_cycle must get past the readiness check when no real
    training is in progress and enough samples exist.

    Before the fix this always failed with "Training already in progress"
    because current_training was set before the check.
    """
    manager = _make_manager()

    # Stub out the heavy phases so we only exercise the readiness gate.
    # We let the method run until it hits prepare_training_data (Phase 2),
    # then raise to stop early — the important assertion is that we got
    # past the readiness check without being rejected.
    async def _fake_prepare():
        return {"success": False, "error": "stopped early for test"}

    manager.prepare_training_data = _fake_prepare  # type: ignore[assignment]

    result = await manager.run_training_cycle()

    # We should NOT have been rejected at the readiness phase.
    assert result.get("phase") != "readiness_check", (
        f"Readiness check rejected: {result.get('error')}"
    )
    # We should have reached data_preparation (phase 2) and failed there
    # because our stub returns success=False.
    assert result.get("phase") == "data_preparation"


@pytest.mark.asyncio
async def test_readiness_rejects_genuinely_concurrent_training():
    """If a training cycle is genuinely already in progress (current_training
    set externally / by a prior incomplete run), the readiness check must
    still reject a second call.
    """
    manager = _make_manager()

    # Simulate a genuinely in-progress training by setting current_training
    # BEFORE calling check_training_readiness (the normal guard path).
    manager.current_training = {
        "start_time": "2026-01-01T00:00:00",
        "status": "running",
        "phase": "fine_tuning",
    }

    readiness = await manager.check_training_readiness()
    assert readiness["ready"] is False
    assert "already in progress" in readiness["reason"]


@pytest.mark.asyncio
async def test_check_training_readiness_no_false_positive():
    """check_training_readiness must not reject when current_training is None
    and all other conditions are met.
    """
    manager = _make_manager()
    assert manager.current_training is None

    readiness = await manager.check_training_readiness()
    assert readiness["ready"] is True


@pytest.mark.asyncio
async def test_run_training_cycle_resets_state_on_readiness_failure():
    """After a readiness failure, current_training must remain None (not leak)."""
    manager = _make_manager()
    # Override to report fewer candidates than required so readiness fails.
    manager.data_collector.get_statistics.return_value = {"training_candidates": 0}

    result = await manager.run_training_cycle()
    assert result["success"] is False
    assert result["phase"] == "readiness_check"
    assert manager.current_training is None
