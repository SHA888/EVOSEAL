# NOTE: Run pytest from the project root for imports to work:
#   pytest tests/unit/models/test_evaluation.py
from datetime import datetime

import pytest

from evoseal.models.evaluation import EvaluationResult, TestCaseResult

ACCURACY = 0.95


def test_evaluation_result_creation():
    result = EvaluationResult(
        code_archive_id="abc123",
        metrics={"accuracy": ACCURACY, "precision": 0.8},
        test_case_results=[
            TestCaseResult(name="test_one", passed=True),
            TestCaseResult(name="test_two", passed=False, message="Failed due to X"),
        ],
        notes="Initial evaluation",
        created_by="tester",
    )
    assert result.code_archive_id == "abc123"
    assert result.metrics["accuracy"] == ACCURACY
    assert result.test_case_results[1].passed is False
    assert result.notes == "Initial evaluation"
    assert result.created_by == "tester"
    assert isinstance(result.timestamp, datetime)


def test_metric_validation_error():
    with pytest.raises(ValueError) as exc:
        EvaluationResult(
            code_archive_id="def456",
            metrics={"accuracy": 1.5},  # Invalid, out of bounds
        )
    assert "between 0 and 1" in str(exc.value)


def test_serialization_roundtrip():
    result = EvaluationResult(
        code_archive_id="ghi789",
        metrics={"recall": 0.7},
        test_case_results=[TestCaseResult(name="test_a", passed=True)],
    )
    json_str = result.to_json()
    loaded = EvaluationResult.from_json(json_str)
    assert loaded.code_archive_id == result.code_archive_id
    assert loaded.metrics == result.metrics
    assert loaded.test_case_results[0].name == "test_a"
