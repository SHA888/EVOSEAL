from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, cast
from uuid import uuid4

from pydantic import BaseModel, Field, validator


class TestCaseResult(BaseModel):
    name: str
    passed: bool
    message: str | None = None


class EvaluationResult(BaseModel):
    """Stores evaluation metrics and test outcomes for a code archive."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique evaluation result ID")
    code_archive_id: str = Field(..., description="Reference to associated CodeArchive (by ID)")
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Performance metrics (accuracy, precision, recall, etc.)",
    )
    test_case_results: list[TestCaseResult] = Field(
        default_factory=list, description="Results for each test case"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Evaluation timestamp (UTC)",
    )
    notes: str | None = Field(default=None, description="Optional notes or comments")
    created_by: str | None = Field(
        default=None, description="User or system that created this evaluation"
    )

    @validator("metrics")
    @classmethod
    def validate_metrics(cls, v: dict[str, float]) -> dict[str, float]:
        # Example: enforce 0 <= value <= 1 for common metrics
        bounded_metrics = {"accuracy", "precision", "recall", "f1", "auc"}
        for key, value in v.items():
            if key.lower() in bounded_metrics:
                if not (0.0 <= value <= 1.0):
                    raise ValueError(f"Metric '{key}' must be between 0 and 1 (got {value})")
        return v

    def to_json(self, **kwargs: Any) -> str:
        return str(self.model_dump_json(**kwargs))

    @classmethod
    def from_json(cls, json_str: str, **kwargs: Any) -> EvaluationResult:
        result = cls.model_validate_json(str(json_str), **kwargs)
        assert isinstance(result, EvaluationResult)
        return result
