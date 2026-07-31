"""Extended unit tests for Evaluator.

Covers edge cases: empty results, missing metrics, unknown strategy,
score bounds, and generate_feedback paths not covered by the original test_evaluator.py.
"""

from __future__ import annotations

import pytest

from evoseal.core.evaluator import Evaluator


def test_evaluate_empty_results():
    evaluator = Evaluator()
    results = evaluator.evaluate([])
    assert results == []


def test_evaluate_missing_metrics_default_to_zero():
    """Missing metric keys should default to 0.0 in the score calculation."""
    evaluator = Evaluator()
    results = evaluator.evaluate([{}])
    assert len(results) == 1
    assert results[0]["score"] == 0.0


def test_evaluate_partial_metrics():
    """Only pass_rate present; coverage and quality default to 0."""
    evaluator = Evaluator()
    results = evaluator.evaluate([{"pass_rate": 1.0}])
    # score = 0.7 * 1.0 + 0.2 * 0.0 + 0.1 * 0.0 = 0.7
    assert abs(results[0]["score"] - 0.7) < 1e-6


def test_evaluate_unknown_strategy_falls_back_to_default():
    """Unknown strategy falls back to default_strategy (no raise)."""
    evaluator = Evaluator()
    results = evaluator.evaluate(
        [{"pass_rate": 1.0, "coverage": 1.0, "quality": 1.0}], strategy="nonexistent"
    )
    assert len(results) == 1
    assert "score" in results[0]


def test_evaluate_all_metrics_perfect():
    evaluator = Evaluator()
    results = evaluator.evaluate([{"pass_rate": 1.0, "coverage": 1.0, "quality": 1.0}])
    # score = 0.7 * 1.0 + 0.2 * 1.0 + 0.1 * 1.0 = 1.0
    assert abs(results[0]["score"] - 1.0) < 1e-6


def test_evaluate_all_metrics_zero():
    evaluator = Evaluator()
    results = evaluator.evaluate([{"pass_rate": 0.0, "coverage": 0.0, "quality": 0.0}])
    assert results[0]["score"] == 0.0


def test_feedback_contains_all_metrics():
    evaluator = Evaluator()
    result = evaluator.evaluate([{"pass_rate": 0.5, "coverage": 0.3, "quality": 0.4}])[0]
    feedback = result["feedback"]
    assert "pass_rate" in feedback
    assert "coverage" in feedback
    assert "quality" in feedback


def test_feedback_no_issues_when_perfect():
    evaluator = Evaluator()
    result = evaluator.evaluate([{"pass_rate": 1.0, "coverage": 1.0, "quality": 1.0}])[0]
    feedback = result["feedback"]
    assert "Some tests failed" not in feedback
    assert "Low coverage" not in feedback
    assert "Code quality could be improved" not in feedback


def test_feedback_flags_low_coverage():
    evaluator = Evaluator()
    result = evaluator.evaluate([{"pass_rate": 1.0, "coverage": 0.5, "quality": 1.0}])[0]
    assert "Low coverage" in result["feedback"]


def test_feedback_flags_low_quality():
    evaluator = Evaluator()
    result = evaluator.evaluate([{"pass_rate": 1.0, "coverage": 1.0, "quality": 0.3}])[0]
    assert "Code quality could be improved" in result["feedback"]


def test_custom_default_weights():
    """Custom default_weights at construction time should be used when no weights arg."""
    evaluator = Evaluator(default_weights={"pass_rate": 1.0, "coverage": 0.0, "quality": 0.0})
    results = evaluator.evaluate([{"pass_rate": 0.5, "coverage": 1.0, "quality": 1.0}])
    assert abs(results[0]["score"] - 0.5) < 1e-6


def test_add_strategy_overwrites_default():
    """Adding a strategy with name 'default' should replace the built-in."""
    evaluator = Evaluator()

    def always_one(result, weights):
        return {"score": 1.0, "feedback": "always one", **result}

    evaluator.add_strategy("default", always_one)
    results = evaluator.evaluate([{"pass_rate": 0.0}])
    assert results[0]["score"] == 1.0


def test_evaluate_multiple_results():
    """Ensure each result is evaluated independently."""
    evaluator = Evaluator()
    test_results = [
        {"pass_rate": 1.0, "coverage": 1.0, "quality": 1.0},
        {"pass_rate": 0.0, "coverage": 0.0, "quality": 0.0},
        {"pass_rate": 0.5, "coverage": 0.5, "quality": 0.5},
    ]
    results = evaluator.evaluate(test_results)
    assert len(results) == 3
    assert results[0]["score"] > results[2]["score"] > results[1]["score"]
