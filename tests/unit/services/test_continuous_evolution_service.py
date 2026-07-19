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
