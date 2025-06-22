"""
Unit tests for the Evaluator class in evoseal.

Covers default strategy, feedback, weights, and extensibility.
"""

import pytest

from evoseal.core.evaluator import Evaluator

TOLERANCE = 1e-6


def test_default_evaluation_scores_and_feedback():
    evaluator = Evaluator()
    test_results = [
        {"pass_rate": 1.0, "coverage": 0.9, "quality": 0.8},
        {"pass_rate": 0.5, "coverage": 0.7, "quality": 0.6},
        {"pass_rate": 0.0, "coverage": 0.5, "quality": 0.3},
    ]
    results = evaluator.evaluate(test_results)
    assert results[0]["score"] > results[1]["score"] > results[2]["score"]
    for r in results:
        assert "feedback" in r
        assert isinstance(r["feedback"], str)
        assert "score" in r


def test_custom_weights_affect_score():
    evaluator = Evaluator()
    test_results = [
        {"pass_rate": 0.8, "coverage": 0.5, "quality": 0.5},
    ]
    # Emphasize coverage
    weights = {"pass_rate": 0.2, "coverage": 0.7, "quality": 0.1}
    result = evaluator.evaluate(test_results, weights=weights)[0]
    assert abs(result["score"] - (0.2 * 0.8 + 0.7 * 0.5 + 0.1 * 0.5)) < TOLERANCE


def test_add_strategy_and_use():
    evaluator = Evaluator()

    def reverse_strategy(result, weights):
        # Lower pass_rate is better!
        score = 1.0 - result.get("pass_rate", 0.0)
        return {"score": score, "feedback": f"Reverse: {score:.2f}", **result}

    evaluator.add_strategy("reverse", reverse_strategy)
    test_results = [{"pass_rate": 0.0}, {"pass_rate": 1.0}]
    results = evaluator.evaluate(test_results, strategy="reverse")
    assert results[0]["score"] > results[1]["score"]
    for r in results:
        assert r["feedback"].startswith("Reverse:")


def test_feedback_content():
    evaluator = Evaluator()
    test_results = [{"pass_rate": 0.6, "coverage": 0.6, "quality": 0.6}]
    result = evaluator.evaluate(test_results)[0]
    assert "Some tests failed" in result["feedback"]
    assert "Low coverage" in result["feedback"]
    assert "Code quality could be improved" in result["feedback"]
