"""Data models for the prompt-level co-evolution loop.

These are lightweight, serializable records that flow through the loop:
a task is given to the coder, the coder produces a :class:`CodeAttempt`, the
reviewer produces a :class:`ReviewCritique`, and (when the critique is weak) the
coder's system prompt is evolved into a new :class:`PromptVersion`. Each full
pass is summarized by a :class:`CoevolutionCycleResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from evoseal.providers.local_models import AgentRole

__all__ = [
    "AgentRole",
    "TaskSpec",
    "CodeAttempt",
    "ReviewCritique",
    "PromptVersion",
    "CoevolutionCycleResult",
]


@dataclass
class TaskSpec:
    """A coding task presented to the coder agent."""

    id: str
    description: str
    acceptance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "description": self.description, "acceptance": self.acceptance}


@dataclass
class CodeAttempt:
    """The coder's response to a task."""

    task_id: str
    model: str
    code: str
    raw_response: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model": self.model,
            "code": self.code,
            "raw_response": self.raw_response,
        }


@dataclass
class ReviewCritique:
    """The reviewer's evaluation of a :class:`CodeAttempt`.

    ``score`` is normalized to ``0.0``-``1.0`` (higher is better).
    """

    task_id: str
    model: str
    score: float
    issues: list[str] = field(default_factory=list)
    summary: str = ""
    raw: str = ""

    def passed(self, threshold: float) -> bool:
        """True when the score meets or exceeds ``threshold``."""
        return self.score >= threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model": self.model,
            "score": self.score,
            "issues": list(self.issues),
            "summary": self.summary,
            "raw": self.raw,
        }


@dataclass
class PromptVersion:
    """A versioned system prompt for one agent role, with lineage for rollback."""

    version_id: str
    role: str
    prompt_text: str
    parent_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    rationale: str = ""
    score: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "role": self.role,
            "prompt_text": self.prompt_text,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "rationale": self.rationale,
            "score": self.score,
            "metrics": dict(self.metrics),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptVersion:
        return cls(
            version_id=data["version_id"],
            role=data["role"],
            prompt_text=data["prompt_text"],
            parent_id=data.get("parent_id"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            rationale=data.get("rationale", ""),
            score=data.get("score"),
            metrics=data.get("metrics", {}),
        )


@dataclass
class CoevolutionCycleResult:
    """Summary of one generate -> review -> (maybe) evolve pass."""

    cycle_id: str
    task_id: str
    attempt: CodeAttempt
    critique: ReviewCritique
    prompt_before_id: str
    score_before: float
    evolved: bool = False
    accepted: bool = False
    prompt_after_id: str | None = None
    score_after: float | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "task_id": self.task_id,
            "attempt": self.attempt.to_dict(),
            "critique": self.critique.to_dict(),
            "prompt_before_id": self.prompt_before_id,
            "score_before": self.score_before,
            "evolved": self.evolved,
            "accepted": self.accepted,
            "prompt_after_id": self.prompt_after_id,
            "score_after": self.score_after,
            "reason": self.reason,
        }
