"""
Evaluator class for assessing the fitness of code variants based on test results,
code quality metrics, and configurable criteria. Supports multiple strategies and
provides feedback on scoring.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict, TypeVar

# Type variables for generic types
T = TypeVar("T")


# Type aliases for better readability
class EvaluationResult(TypedDict, total=False):
    """Type definition for evaluation results."""

    success: bool
    score: float
    metrics: dict[str, float]
    feedback: str


COVERAGE_THRESHOLD = 0.8
QUALITY_THRESHOLD = 0.7


class Evaluator:
    """Evaluates code variants based on test results and quality metrics."""

    def __init__(
        self,
        strategies: (
            dict[str, Callable[[dict[str, Any], dict[str, float]], dict[str, Any]]] | None
        ) = None,
        default_weights: dict[str, float] | None = None,
    ) -> None:
        self.strategies = strategies or {"default": self.default_strategy}
        self.default_weights = default_weights or {
            "pass_rate": 0.7,
            "coverage": 0.2,
            "quality": 0.1,
        }

    def evaluate(
        self,
        test_results: list[dict[str, Any]],
        strategy: str = "default",
        weights: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Calculate fitness scores for each code variant based on test results and metrics.
        Returns a list of dicts with 'score' and 'feedback' for each variant.
        """
        strat = self.strategies.get(strategy, self.default_strategy)
        weights = weights or self.default_weights
        return [strat(result, weights) for result in test_results]

    def default_strategy(self, result: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
        """
        Default scoring: weighted sum of pass rate, coverage, and code quality.
        Expects result to have 'pass_rate', 'coverage', and 'quality' keys (0.0-1.0).
        """
        score = (
            weights.get("pass_rate", 0.7) * result.get("pass_rate", 0.0)
            + weights.get("coverage", 0.2) * result.get("coverage", 0.0)
            + weights.get("quality", 0.1) * result.get("quality", 0.0)
        )
        feedback = self.generate_feedback(result, weights, score)
        return {"score": score, "feedback": feedback, **result}

    def generate_feedback(
        self, result: dict[str, Any], weights: dict[str, float], score: float
    ) -> str:
        """
        Generate human-readable feedback explaining the score.
        """
        lines = [f"Total score: {score:.2f}"]
        for metric in ["pass_rate", "coverage", "quality"]:
            val = result.get(metric, 0.0)
            lines.append(f"{metric}: {val:.2f} (weight {weights.get(metric, 0.0):.2f})")
        if result.get("pass_rate", 0.0) < 1.0:
            lines.append("Some tests failed. Improve pass rate for higher score.")
        if result.get("coverage", 0.0) < COVERAGE_THRESHOLD:
            lines.append("Low coverage. Add more tests.")
        if result.get("quality", 0.0) < QUALITY_THRESHOLD:
            lines.append("Code quality could be improved.")
        return " | ".join(lines)

    def add_strategy(self, name: str, func: Callable) -> None:
        """Register a new evaluation strategy by name."""
        self.strategies[name] = func
