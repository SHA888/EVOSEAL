"""Tests for FeedbackStore integration in EvolutionPipeline.

Verifies that when human_feedback_required is enabled and a FeedbackStore
is injected, the pipeline gates improvements behind human approval.
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest

from evoseal.core.feedback_store import FeedbackStore


def _ensure_real_pipeline_module():
    """Undo sys.modules poisoning from other tests."""
    mod = sys.modules.get("evoseal.core.evolution_pipeline")
    if mod is not None and type(mod).__name__ == "MagicMock":
        for key in list(sys.modules):
            if key.startswith("evoseal.core.evolution_pipeline"):
                del sys.modules[key]


def _make_pipeline(
    feedback_store=None,
    human_feedback_required=False,
    feedback_timeout=10.0,
    feedback_poll_interval=0.05,
):
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

        pipeline = EvolutionPipeline(
            config={
                "human_feedback_required": human_feedback_required,
                "feedback_poll_interval": feedback_poll_interval,
                "feedback_timeout": feedback_timeout,
            },
            feedback_store=feedback_store,
        )
        return pipeline


class TestPipelineFeedbackStoreInit:
    """EvolutionPipeline accepts and stores a FeedbackStore."""

    def test_default_no_feedback_store(self):
        pipeline = _make_pipeline()
        assert pipeline.feedback_store is None

    def test_injected_feedback_store(self):
        store = FeedbackStore()
        pipeline = _make_pipeline(feedback_store=store)
        assert pipeline.feedback_store is store

    def test_config_defaults(self):
        """EvolutionConfig dataclass defaults are correct."""
        from evoseal.core.evolution_pipeline import EvolutionConfig

        cfg = EvolutionConfig()
        assert cfg.human_feedback_required is False
        assert cfg.feedback_poll_interval == 5.0
        assert cfg.feedback_timeout == 600.0


class TestPipelineFeedbackGating:
    """When human_feedback_required=True, improvements are gated on approval."""

    def test_no_store_auto_approves(self):
        """Without a feedback_store, improvements pass through normally with a warning."""
        pipeline = _make_pipeline(feedback_store=None, human_feedback_required=True)
        results = asyncio.run(pipeline.run_evolution_cycle(iterations=1))
        assert isinstance(results, list)
        assert len(results) == 1

    def test_feedback_not_required_skips_gating(self):
        """When human_feedback_required=False, store is not consulted."""
        store = FeedbackStore()
        pipeline = _make_pipeline(feedback_store=store, human_feedback_required=False)
        results = asyncio.run(pipeline.run_evolution_cycle(iterations=1))
        assert len(results) == 1
        # No proposals should have been submitted
        assert len(store.get_all()) == 0

    def test_feedback_required_submits_proposal(self):
        """When human_feedback_required=True and store present, a proposal is submitted."""
        store = FeedbackStore()

        # Pre-approve any proposals that appear (in a background task)
        async def auto_approve():
            await asyncio.sleep(0.2)
            for p in store.get_pending():
                store.approve(p.id, decided_by="test")

        # Run both concurrently
        async def run():
            # Start auto-approver
            task = asyncio.create_task(auto_approve())
            pipeline = _make_pipeline(
                feedback_store=store, human_feedback_required=True, feedback_timeout=5.0
            )
            results = await pipeline.run_evolution_cycle(iterations=1)
            await task
            return results

        results = asyncio.run(run())
        assert len(results) == 1
        # A proposal should have been submitted
        assert len(store.get_all()) >= 1
        # The proposal should be approved
        assert store.get_all()[0].decision.value == "approved"

    def test_feedback_rejected_stops_iteration(self):
        """Rejected feedback marks the iteration as not an improvement."""
        store = FeedbackStore()

        async def auto_reject():
            await asyncio.sleep(0.2)
            for p in store.get_pending():
                store.reject(p.id, decided_by="test", reason="too risky")

        async def run():
            task = asyncio.create_task(auto_reject())
            pipeline = _make_pipeline(
                feedback_store=store, human_feedback_required=True, feedback_timeout=5.0
            )
            results = await pipeline.run_evolution_cycle(iterations=1)
            await task
            return results

        results = asyncio.run(run())
        assert len(results) == 1
        result = results[0]
        # The iteration should report feedback was rejected
        assert result.get("feedback_decision") == "rejected"

    def test_feedback_timeout_stops_iteration(self):
        """Timeout waiting for feedback marks iteration as timeout."""
        store = FeedbackStore()
        # Use very short timeout
        pipeline = _make_pipeline(
            feedback_store=store,
            human_feedback_required=True,
            feedback_timeout=0.2,
            feedback_poll_interval=0.05,
        )
        results = asyncio.run(pipeline.run_evolution_cycle(iterations=1))
        assert len(results) == 1
        result = results[0]
        assert result.get("feedback_decision") == "timeout"


class TestFeedbackZeroTimeout:
    """feedback_timeout <= 0 should expire the proposal immediately."""

    def test_zero_timeout_expires_proposal(self):
        store = FeedbackStore()
        pipeline = _make_pipeline(
            feedback_store=store,
            human_feedback_required=True,
            feedback_timeout=0,
        )
        results = asyncio.run(pipeline.run_evolution_cycle(iterations=1))
        assert len(results) == 1
        assert results[0].get("feedback_decision") == "timeout"
        # The proposal should be expired, not left PENDING
        proposals = store.get_all()
        assert len(proposals) == 1
        assert proposals[0].decision.value == "expired"

    def test_negative_timeout_expires_proposal(self):
        store = FeedbackStore()
        pipeline = _make_pipeline(
            feedback_store=store,
            human_feedback_required=True,
            feedback_timeout=-5,
        )
        results = asyncio.run(pipeline.run_evolution_cycle(iterations=1))
        assert len(results) == 1
        assert results[0].get("feedback_decision") == "timeout"
        proposals = store.get_all()
        assert len(proposals) == 1
        assert proposals[0].decision.value == "expired"


class TestFeedbackPollException:
    """Exception during polling should degrade gracefully."""

    def test_poll_expire_both_fail_returns_timeout(self):
        """If get_proposal raises AND expire_proposal raises, still return timeout."""
        store = FeedbackStore()
        proposal = store.submit_proposal(title="Test", description="desc")

        # Make both get_proposal and expire_proposal raise
        store.get_proposal = MagicMock(side_effect=RuntimeError("store down"))
        store.expire_proposal = MagicMock(side_effect=RuntimeError("store still down"))

        pipeline = _make_pipeline(
            feedback_store=store,
            human_feedback_required=True,
            feedback_timeout=10.0,
            feedback_poll_interval=0.05,
        )
        results = asyncio.run(pipeline.run_evolution_cycle(iterations=1))
        assert len(results) == 1
        assert results[0].get("feedback_decision") == "timeout"


class TestFeedbackStoreExpire:
    """FeedbackStore.expire_proposal marks proposals as expired."""

    def test_expire_pending_proposal(self):
        store = FeedbackStore()
        proposal = store.submit_proposal(title="Test", description="desc")
        result = store.expire_proposal(proposal.id)
        assert result is not None
        assert result.decision.value == "expired"
        assert result.decided_by == "system"
        assert "timed out" in result.reason

    def test_expire_already_decided_proposal(self):
        store = FeedbackStore()
        proposal = store.submit_proposal(title="Test", description="desc")
        store.approve(proposal.id)
        result = store.expire_proposal(proposal.id)
        assert result is None

    def test_expire_nonexistent_proposal(self):
        store = FeedbackStore()
        result = store.expire_proposal("nonexistent")
        assert result is None

    def test_stats_include_expired(self):
        store = FeedbackStore()
        p1 = store.submit_proposal(title="A", description="a")
        p2 = store.submit_proposal(title="B", description="b")
        store.expire_proposal(p1.id)
        store.approve(p2.id)
        stats = store.get_stats()
        assert stats["expired"] == 1
        assert stats["approved"] == 1
        assert stats["total"] == 2


class TestPipelineFeedbackConfig:
    """Config fields for feedback gating."""

    def test_custom_poll_interval(self):
        pipeline = _make_pipeline()
        pipeline.config.feedback_poll_interval = 1.0
        assert pipeline.config.feedback_poll_interval == 1.0

    def test_custom_timeout(self):
        pipeline = _make_pipeline()
        pipeline.config.feedback_timeout = 120.0
        assert pipeline.config.feedback_timeout == 120.0

    def test_human_feedback_required_toggle(self):
        pipeline = _make_pipeline()
        pipeline.config.human_feedback_required = True
        assert pipeline.config.human_feedback_required is True
