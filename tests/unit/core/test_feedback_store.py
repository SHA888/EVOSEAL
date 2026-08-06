"""Tests for FeedbackStore — human-in-the-loop feedback for self-modifications."""

from __future__ import annotations

import pytest

from evoseal.core.feedback_store import FeedbackDecision, FeedbackStore, ModificationProposal


@pytest.fixture
def store():
    return FeedbackStore()


class TestSubmitProposal:
    def test_submit_returns_proposal(self, store):
        p = store.submit_proposal("Fix bug", "Fix the null pointer", [{"path": "main.py"}])
        assert isinstance(p, ModificationProposal)
        assert p.title == "Fix bug"
        assert p.description == "Fix the null pointer"
        assert p.file_changes == [{"path": "main.py"}]
        assert p.decision == FeedbackDecision.PENDING
        assert p.id  # non-empty

    def test_submit_defaults(self, store):
        p = store.submit_proposal("Title", "Desc")
        assert p.file_changes == []
        assert p.metadata == {}
        assert p.decided_at is None
        assert p.decided_by is None
        assert p.reason is None

    def test_submit_with_metadata(self, store):
        p = store.submit_proposal("T", "D", metadata={"fitness": 0.9})
        assert p.metadata == {"fitness": 0.9}

    def test_unique_ids(self, store):
        p1 = store.submit_proposal("A", "a")
        p2 = store.submit_proposal("B", "b")
        assert p1.id != p2.id


class TestGetProposal:
    def test_get_existing(self, store):
        p = store.submit_proposal("T", "D")
        assert store.get_proposal(p.id) is p

    def test_get_nonexistent(self, store):
        assert store.get_proposal("nonexistent") is None


class TestGetPending:
    def test_empty_store(self, store):
        assert store.get_pending() == []

    def test_only_pending_returned(self, store):
        p1 = store.submit_proposal("A", "a")
        p2 = store.submit_proposal("B", "b")
        store.approve(p1.id)
        pending = store.get_pending()
        assert len(pending) == 1
        assert pending[0].id == p2.id

    def test_newest_first(self, store):
        p1 = store.submit_proposal("A", "a")
        p2 = store.submit_proposal("B", "b")
        pending = store.get_pending()
        assert pending[0].id == p2.id
        assert pending[1].id == p1.id


class TestApprove:
    def test_approve_sets_fields(self, store):
        p = store.submit_proposal("T", "D")
        result = store.approve(p.id, decided_by="alice", reason="looks good")
        assert result is not None
        assert result.decision == FeedbackDecision.APPROVED
        assert result.decided_by == "alice"
        assert result.reason == "looks good"
        assert result.decided_at is not None

    def test_approve_nonexistent(self, store):
        assert store.approve("nope") is None

    def test_approve_already_decided(self, store):
        p = store.submit_proposal("T", "D")
        store.approve(p.id)
        assert store.approve(p.id) is None  # can't re-approve

    def test_approve_rejected_proposal(self, store):
        p = store.submit_proposal("T", "D")
        store.reject(p.id)
        assert store.approve(p.id) is None


class TestReject:
    def test_reject_sets_fields(self, store):
        p = store.submit_proposal("T", "D")
        result = store.reject(p.id, decided_by="bob", reason="too risky")
        assert result is not None
        assert result.decision == FeedbackDecision.REJECTED
        assert result.decided_by == "bob"
        assert result.reason == "too risky"

    def test_reject_nonexistent(self, store):
        assert store.reject("nope") is None

    def test_reject_already_approved(self, store):
        p = store.submit_proposal("T", "D")
        store.approve(p.id)
        assert store.reject(p.id) is None


class TestGetStats:
    def test_empty(self, store):
        stats = store.get_stats()
        assert stats == {
            "total": 0,
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "acceptance_rate": None,
        }

    def test_mixed(self, store):
        store.submit_proposal("A", "a")
        p2 = store.submit_proposal("B", "b")
        p3 = store.submit_proposal("C", "c")
        store.approve(p2.id)
        store.reject(p3.id)
        stats = store.get_stats()
        assert stats["total"] == 3
        assert stats["pending"] == 1
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["acceptance_rate"] == 50.0

    def test_all_approved(self, store):
        p = store.submit_proposal("T", "D")
        store.approve(p.id)
        stats = store.get_stats()
        assert stats["acceptance_rate"] == 100.0


class TestToDict:
    def test_round_trip(self, store):
        p = store.submit_proposal("T", "D", [{"path": "x.py"}], {"k": "v"})
        d = p.to_dict()
        assert d["title"] == "T"
        assert d["description"] == "D"
        assert d["file_changes"] == [{"path": "x.py"}]
        assert d["metadata"] == {"k": "v"}
        assert d["decision"] == "pending"
        assert d["decided_at"] is None

    def test_decided_to_dict(self, store):
        p = store.submit_proposal("T", "D")
        store.approve(p.id, decided_by="me", reason="ok")
        d = p.to_dict()
        assert d["decision"] == "approved"
        assert d["decided_by"] == "me"
        assert d["reason"] == "ok"
        assert d["decided_at"] is not None


class TestGetAll:
    def test_returns_all(self, store):
        store.submit_proposal("A", "a")
        p2 = store.submit_proposal("B", "b")
        store.approve(p2.id)
        all_proposals = store.get_all()
        assert len(all_proposals) == 2
