"""Regression tests for EvolutionPipeline._validate_improvement.

The _validate_improvement method is the actual validation gate wired into
the evolution loop.  It was previously a hardcoded stub that always returned
True (see TODO.md P0 — "ImprovementValidator is non-functional").  These
tests verify the real implementation:

- First iteration (fewer than 2 metric entries) → always accepted.
- Improvement in metrics → accepted.
- Regression in metrics → rejected.
- Exception during validation → rejected (fail-closed).
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_real_pipeline_module():
    """Undo sys.modules poisoning from other tests that replace the module
    with a MagicMock at import time."""
    mod = sys.modules.get("evoseal.core.evolution_pipeline")
    if mod is not None and type(mod).__name__ == "MagicMock":
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
        patch("evoseal.core.evolution_pipeline.ImprovementValidator") as mock_validator_cls,
        patch("evoseal.core.evolution_pipeline.MetricsTracker") as mock_tracker_cls,
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
        # Stash mock references for test manipulation
        pipeline._mock_tracker = mock_tracker_cls.return_value
        pipeline._mock_validator = mock_validator_cls.return_value
        return pipeline


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateImprovement:
    """Test the _validate_improvement gate on EvolutionPipeline."""

    def test_first_iteration_always_accepted(self):
        """When fewer than 2 metric entries exist, validation passes.

        The first iteration has nothing to compare against, so it must be
        accepted to bootstrap the evolution loop.
        """
        pipeline = _make_pipeline()
        pipeline._mock_tracker.get_metrics_history.return_value = []

        result = asyncio.run(pipeline._validate_improvement({"test_type": "unit"}))
        assert result is True

    def test_single_metric_entry_always_accepted(self):
        """With exactly 1 metric entry, there is no baseline — accept."""
        pipeline = _make_pipeline()
        pipeline._mock_tracker.get_metrics_history.return_value = [MagicMock()]

        result = asyncio.run(pipeline._validate_improvement({"test_type": "unit"}))
        assert result is True

    def test_improvement_accepted(self):
        """When the validator reports is_improvement=True, accept."""
        pipeline = _make_pipeline()
        pipeline._mock_tracker.get_metrics_history.return_value = [
            MagicMock(),
            MagicMock(),
        ]
        pipeline._mock_validator.validate_improvement.return_value = {
            "is_improvement": True,
            "score": 85.0,
            "required_passed": True,
        }

        result = asyncio.run(pipeline._validate_improvement({"test_type": "unit"}))
        assert result is True

        # Validator must have been called with correct indices
        pipeline._mock_validator.validate_improvement.assert_called_once_with(0, 1, "unit")

    def test_regression_rejected(self):
        """When the validator reports is_improvement=False, reject."""
        pipeline = _make_pipeline()
        pipeline._mock_tracker.get_metrics_history.return_value = [
            MagicMock(),
            MagicMock(),
        ]
        pipeline._mock_validator.validate_improvement.return_value = {
            "is_improvement": False,
            "score": 20.0,
            "required_passed": False,
        }

        result = asyncio.run(pipeline._validate_improvement({"test_type": "unit"}))
        assert result is False

    def test_exception_during_validation_rejected(self):
        """If the validator raises, _validate_improvement must return False.

        This is the fail-closed contract: any error during validation
        means the self-modification is rejected.
        """
        pipeline = _make_pipeline()
        pipeline._mock_tracker.get_metrics_history.return_value = [
            MagicMock(),
            MagicMock(),
        ]
        pipeline._mock_validator.validate_improvement.side_effect = RuntimeError(
            "metrics DB corrupted"
        )

        result = asyncio.run(pipeline._validate_improvement({"test_type": "unit"}))
        assert result is False

    def test_missing_is_improvement_key_rejected(self):
        """If the validator returns a dict without 'is_improvement', reject.

        A malformed validator response should not be treated as approval.
        """
        pipeline = _make_pipeline()
        pipeline._mock_tracker.get_metrics_history.return_value = [
            MagicMock(),
            MagicMock(),
        ]
        pipeline._mock_validator.validate_improvement.return_value = {
            "score": 50.0,
            # 'is_improvement' key missing
        }

        result = asyncio.run(pipeline._validate_improvement({"test_type": "unit"}))
        assert result is False

    def test_none_test_type_passes_through(self):
        """test_type=None should be forwarded to the tracker and validator."""
        pipeline = _make_pipeline()
        pipeline._mock_tracker.get_metrics_history.return_value = [
            MagicMock(),
            MagicMock(),
        ]
        pipeline._mock_validator.validate_improvement.return_value = {
            "is_improvement": True,
            "score": 90.0,
        }

        result = asyncio.run(pipeline._validate_improvement({"test_type": None}))
        assert result is True

        pipeline._mock_tracker.get_metrics_history.assert_called_once_with(None)
        pipeline._mock_validator.validate_improvement.assert_called_once_with(0, 1, None)
