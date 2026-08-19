"""
Human-in-the-loop feedback store for self-modification proposals.

Provides an in-memory store where pending self-modifications are queued
for human review. Developers can approve or reject proposals through the
dashboard, and acceptance-rate metrics are tracked automatically.

This is the first integration point for the human-in-the-loop feedback
interface described in TODO.md. Future work may add persistence, webhook
notifications, and pipeline integration (gating self-modifications behind
approval).
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class FeedbackDecision(str, Enum):
    """Possible decisions on a modification proposal."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ModificationProposal:
    """A proposed self-modification awaiting human review."""

    id: str
    title: str
    description: str
    file_changes: list[dict[str, Any]]
    proposed_at: str  # ISO 8601
    decision: FeedbackDecision = FeedbackDecision.PENDING
    decided_at: str | None = None
    decided_by: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "file_changes": copy.deepcopy(self.file_changes),
            "proposed_at": self.proposed_at,
            "decision": self.decision.value,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "reason": self.reason,
            "metadata": copy.deepcopy(self.metadata),
        }


class FeedbackStore:
    """In-memory store for modification proposals and human feedback.

    Thread-safety note: this implementation is not thread-safe. The
    dashboard runs in a single asyncio event loop, so concurrent access
    from HTTP handlers is serialized. If persistence or multi-process
    access is needed, wrap with a lock or move to a database.

    Memory note: proposals accumulate indefinitely with no eviction,
    expiry, or size cap on ``file_changes``/``metadata``.  This is
    acceptable for short-lived or low-throughput sessions but is an
    unbounded memory-growth path for long-running processes.
    """

    def __init__(self) -> None:
        self._proposals: dict[str, ModificationProposal] = {}

    def submit_proposal(
        self,
        title: str,
        description: str,
        file_changes: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ModificationProposal:
        """Submit a new modification proposal for human review."""
        now = datetime.now(timezone.utc).isoformat()
        proposal = ModificationProposal(
            id=uuid.uuid4().hex,
            title=title,
            description=description,
            file_changes=copy.deepcopy(file_changes) if file_changes else [],
            proposed_at=now,
            metadata=copy.deepcopy(metadata) if metadata else {},
        )
        self._proposals[proposal.id] = proposal
        return proposal

    def get_proposal(self, proposal_id: str) -> ModificationProposal | None:
        """Get a proposal by ID, or None if not found."""
        return self._proposals.get(proposal_id)

    def get_pending(self) -> list[ModificationProposal]:
        """Return all pending proposals, newest first."""
        return sorted(
            [p for p in self._proposals.values() if p.decision == FeedbackDecision.PENDING],
            key=lambda p: p.proposed_at,
            reverse=True,
        )

    def get_all(self) -> list[ModificationProposal]:
        """Return all proposals, newest first."""
        return sorted(
            self._proposals.values(),
            key=lambda p: p.proposed_at,
            reverse=True,
        )

    def approve(
        self,
        proposal_id: str,
        decided_by: str = "operator",
        reason: str | None = None,
    ) -> ModificationProposal | None:
        """Approve a pending proposal. Returns the proposal or None if not found/not pending."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.decision != FeedbackDecision.PENDING:
            return None
        now = datetime.now(timezone.utc).isoformat()
        proposal.decision = FeedbackDecision.APPROVED
        proposal.decided_at = now
        proposal.decided_by = decided_by
        proposal.reason = reason
        return proposal

    def reject(
        self,
        proposal_id: str,
        decided_by: str = "operator",
        reason: str | None = None,
    ) -> ModificationProposal | None:
        """Reject a pending proposal. Returns the proposal or None if not found/not pending."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.decision != FeedbackDecision.PENDING:
            return None
        now = datetime.now(timezone.utc).isoformat()
        proposal.decision = FeedbackDecision.REJECTED
        proposal.decided_at = now
        proposal.decided_by = decided_by
        proposal.reason = reason
        return proposal

    def get_stats(self) -> dict[str, Any]:
        """Return acceptance-rate statistics."""
        total = len(self._proposals)
        pending = sum(1 for p in self._proposals.values() if p.decision == FeedbackDecision.PENDING)
        approved = sum(
            1 for p in self._proposals.values() if p.decision == FeedbackDecision.APPROVED
        )
        rejected = sum(
            1 for p in self._proposals.values() if p.decision == FeedbackDecision.REJECTED
        )
        decided = approved + rejected
        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "acceptance_rate": (approved / decided * 100) if decided > 0 else None,
        }
