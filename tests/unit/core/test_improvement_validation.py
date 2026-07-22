"""Regression tests for improvement validation wiring.

Verifies that:
- A genuine improvement (better metrics) is accepted.
- A regression (worse metrics) is rejected.
- The plumbing between EvolutionPipeline, ImprovementValidator, and
  MetricsTracker works without AttributeError / NameError.
"""

from __future__ import annotations

import pytest

from evoseal.core.improvement_validator import ImprovementValidator
from evoseal.core.metrics_tracker import MetricsTracker, TestMetrics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_metrics(
    *,
    test_type: str = "unit",
    timestamp: str = "2026-01-01T00:00:00Z",
    tests_passed: int = 10,
    tests_failed: int = 0,
    success_rate: float = 100.0,
    duration_sec: float = 1.0,
    memory_mb: float = 50.0,
) -> TestMetrics:
    return TestMetrics(
        test_type=test_type,
        timestamp=timestamp,
        total_tests=tests_passed + tests_failed,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        tests_skipped=0,
        tests_errors=0,
        success_rate=success_rate,
        duration_sec=duration_sec,
        memory_mb=memory_mb,
    )


def _tracker_with_history(metrics_list: list[TestMetrics]) -> MetricsTracker:
    tracker = MetricsTracker()
    tracker.metrics_history = list(metrics_list)
    return tracker


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateImprovementPlumbing:
    """Ensure validate_improvement runs without AttributeError / NameError."""

    def test_returns_dict_with_required_keys(self):
        """validate_improvement must return a dict containing all keys that
        downstream consumers (save_validation_report, display, pipeline) rely
        on — no AttributeError or NameError."""
        tracker = _tracker_with_history(
            [
                _make_metrics(timestamp="2026-01-01T00:00:00Z", success_rate=80.0),
                _make_metrics(timestamp="2026-01-02T00:00:00Z", success_rate=90.0),
            ]
        )
        validator = ImprovementValidator(tracker, min_improvement_score=50.0)

        result = validator.validate_improvement(0, 1, "unit")

        # Core keys
        assert "is_improvement" in result
        assert "score" in result
        assert "required_passed" in result
        assert "meets_score_threshold" in result
        assert "message" in result
        assert isinstance(result["message"], str)
        assert "details" in result
        assert "timestamp" in result

        # Per-detail keys used by display_validation_results
        for detail in result["details"]:
            assert "baseline_value" in detail, detail
            assert "current_value" in detail, detail
            assert "passed" in detail, detail
            assert "improvement_pct" in detail, detail

    def test_save_validation_report_reads_correct_keys(self):
        """save_validation_report must not raise KeyError — verifies the
        passed_required → required_passed mapping fix."""
        tracker = _tracker_with_history(
            [
                _make_metrics(timestamp="2026-01-01T00:00:00Z"),
                _make_metrics(timestamp="2026-01-02T00:00:00Z"),
            ]
        )
        validator = ImprovementValidator(tracker, min_improvement_score=50.0)
        result = validator.validate_improvement(0, 1, "unit")

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            # Must not raise KeyError
            validator.save_validation_report(result, out)
            assert out.exists()


class TestImprovementAccepted:
    """Genuine improvement should be accepted."""

    def test_improvement_returns_true(self):
        """Better success rate + faster duration → is_improvement True."""
        tracker = _tracker_with_history(
            [
                _make_metrics(
                    timestamp="2026-01-01T00:00:00Z",
                    tests_passed=7,
                    tests_failed=3,
                    success_rate=70.0,
                    duration_sec=2.0,
                ),
                _make_metrics(
                    timestamp="2026-01-02T00:00:00Z",
                    tests_passed=10,
                    tests_failed=0,
                    success_rate=100.0,
                    duration_sec=1.0,
                ),
            ]
        )
        validator = ImprovementValidator(tracker, min_improvement_score=50.0)
        result = validator.validate_improvement(0, 1, "unit")
        assert result["is_improvement"] is True


class TestRegressionRejected:
    """A regression should be rejected."""

    def test_regression_returns_false(self):
        """Worse success rate + more failures → is_improvement False."""
        tracker = _tracker_with_history(
            [
                _make_metrics(
                    timestamp="2026-01-01T00:00:00Z",
                    tests_passed=10,
                    tests_failed=0,
                    success_rate=100.0,
                    duration_sec=1.0,
                ),
                _make_metrics(
                    timestamp="2026-01-02T00:00:00Z",
                    tests_passed=5,
                    tests_failed=5,
                    success_rate=50.0,
                    duration_sec=3.0,
                ),
            ]
        )
        validator = ImprovementValidator(tracker, min_improvement_score=50.0)
        result = validator.validate_improvement(0, 1, "unit")
        assert result["is_improvement"] is False
