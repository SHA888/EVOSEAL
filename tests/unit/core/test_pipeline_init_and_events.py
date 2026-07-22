"""Regression tests for evolution_pipeline Bug 1 and Bug 2.

Bug 1: _init_resilience_mechanisms was called without await from sync __init__,
so resilience setup never ran.

Bug 2: Event() constructed with 2 positional args instead of 3, raising
TypeError on every successful run_evolution_cycle.  Also missing await on
publish in run_evolution_cycle.
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest

from evoseal.core.events import Event, EventType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_real_pipeline_module():
    """Undo sys.modules poisoning from test_workflow_integration.py.

    That test replaces evoseal.core.evolution_pipeline with a MagicMock at
    import time.  We detect this and evict the poisoned entry so a fresh
    import gets the real module.
    """
    mod = sys.modules.get("evoseal.core.evolution_pipeline")
    if mod is not None and type(mod).__name__ == "MagicMock":
        # Also evict sub-modules that may have been imported through the mock
        for key in list(sys.modules):
            if key.startswith("evoseal.core.evolution_pipeline"):
                del sys.modules[key]


def _make_pipeline():
    """Build an EvolutionPipeline with heavy deps stubbed out."""
    _ensure_real_pipeline_module()

    with (
        patch("evoseal.core.evolution_pipeline.Settings") as mock_settings_cls,
        patch("evoseal.core.evolution_pipeline.SafetyIntegration"),
        patch("evoseal.core.evolution_pipeline.SandboxedTestRunner"),
        patch("evoseal.core.evolution_pipeline.ImprovementValidator"),
        patch("evoseal.core.evolution_pipeline.MetricsTracker"),
        patch("evoseal.core.evolution_pipeline.BudgetTracker"),
        patch("evoseal.core.evolution_pipeline.IntegrationOrchestrator"),
    ):
        mock_settings = MagicMock()
        mock_settings.budget.max_tokens_per_run = 1_000_000
        mock_settings.budget.warn_at_percent_of_budget = 80
        mock_settings.budget.cost_per_1k_tokens = 0.01
        mock_settings_cls.return_value = mock_settings

        from evoseal.core.evolution_pipeline import EvolutionPipeline

        pipeline = EvolutionPipeline()
        return pipeline


# ---------------------------------------------------------------------------
# Bug 2 — Event() construction + missing await
# ---------------------------------------------------------------------------


class TestRunEvolutionCycleEvents:
    """run_evolution_cycle must not raise TypeError and must publish correct events."""

    def test_completes_without_typeerror(self):
        """A normal run_evolution_cycle must complete without TypeError."""
        pipeline = _make_pipeline()
        results = asyncio.run(pipeline.run_evolution_cycle(iterations=1))
        assert isinstance(results, list)

    def test_publishes_evolution_completed(self):
        """run_evolution_cycle must publish EVOLUTION_COMPLETED with correct data."""
        pipeline = _make_pipeline()

        published_events: list[Event] = []
        original_publish = pipeline.event_bus.publish

        async def capture_publish(event, **kwargs):
            if isinstance(event, Event):
                published_events.append(event)
            return await original_publish(event, **kwargs)

        pipeline.event_bus.publish = capture_publish

        asyncio.run(pipeline.run_evolution_cycle(iterations=1))

        completed = [e for e in published_events if e.event_type == EventType.EVOLUTION_COMPLETED]
        assert len(completed) == 1, f"Expected 1 EVOLUTION_COMPLETED, got {len(completed)}"
        assert completed[0].source == "evolution_pipeline"
        assert "iterations_completed" in completed[0].data
        assert "successful_iterations" in completed[0].data


class TestRunEvolutionCycleWithSafetyEvents:
    """run_evolution_cycle_with_safety must not raise TypeError and must publish correct events."""

    def test_completes_without_typeerror(self):
        """A normal run must complete without TypeError."""
        pipeline = _make_pipeline()
        results = asyncio.run(pipeline.run_evolution_cycle_with_safety(iterations=1))
        assert isinstance(results, list)

    def test_publishes_evolution_completed(self):
        """Must publish EVOLUTION_COMPLETED with correct data."""
        import evoseal.core.evolution_pipeline as ep_mod

        # Re-import to get the real module reference
        _ensure_real_pipeline_module()
        import importlib

        ep_mod = importlib.import_module("evoseal.core.evolution_pipeline")

        pipeline = _make_pipeline()

        published_events: list[Event] = []
        original_publish = ep_mod.event_bus.publish

        async def capture_publish(event, **kwargs):
            if isinstance(event, Event):
                published_events.append(event)
            return await original_publish(event, **kwargs)

        ep_mod.event_bus.publish = capture_publish
        try:
            asyncio.run(pipeline.run_evolution_cycle_with_safety(iterations=1))
        finally:
            ep_mod.event_bus.publish = original_publish

        completed = [e for e in published_events if e.event_type == EventType.EVOLUTION_COMPLETED]
        assert len(completed) == 1, f"Expected 1 EVOLUTION_COMPLETED, got {len(completed)}"
        assert completed[0].source == "evolution_pipeline"
        assert "iterations_completed" in completed[0].data
        assert "accepted_versions" in completed[0].data


# ---------------------------------------------------------------------------
# Bug 1 — resilience init must actually run
# ---------------------------------------------------------------------------


class TestResilienceInit:
    """Resilience mechanisms must be registered after running a cycle."""

    def test_resilience_not_initialized_before_cycle(self):
        """Before any cycle, resilience should NOT be initialized (no sync init)."""
        pipeline = _make_pipeline()
        assert pipeline._resilience_initialized is False

    def test_resilience_initialized_after_cycle(self):
        """After run_evolution_cycle, resilience mechanisms must be registered."""
        from evoseal.core.resilience import resilience_manager

        pipeline = _make_pipeline()

        # Clear any leftover state from previous tests
        resilience_manager.circuit_breakers.clear()

        asyncio.run(pipeline.run_evolution_cycle(iterations=1))

        assert pipeline._resilience_initialized is True
        assert "pipeline" in resilience_manager.circuit_breakers
        assert "openevolve" in resilience_manager.circuit_breakers
        assert "seal" in resilience_manager.circuit_breakers

    def test_resilience_initialized_after_safety_cycle(self):
        """After run_evolution_cycle_with_safety, resilience must be registered."""
        from evoseal.core.resilience import resilience_manager

        pipeline = _make_pipeline()

        # Clear any leftover state from previous tests
        resilience_manager.circuit_breakers.clear()

        asyncio.run(pipeline.run_evolution_cycle_with_safety(iterations=1))

        assert pipeline._resilience_initialized is True
        assert "pipeline" in resilience_manager.circuit_breakers
        assert "openevolve" in resilience_manager.circuit_breakers
        assert "seal" in resilience_manager.circuit_breakers
