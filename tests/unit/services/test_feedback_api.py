"""Tests for MonitoringDashboard feedback API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import TestServer

from evoseal.core.feedback_store import FeedbackStore
from evoseal.services.monitoring_dashboard import MonitoringDashboard


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.get_service_status.return_value = {
        "is_running": True,
        "uptime_seconds": 100,
        "statistics": {},
    }
    svc.bidirectional_manager.get_evolution_status.return_value = {}
    svc.bidirectional_manager.training_manager.get_training_status = AsyncMock(
        return_value={"ready_for_training": False}
    )
    svc.generate_service_report = AsyncMock(return_value={"report": "ok"})
    return svc


@pytest.fixture
def feedback_store():
    return FeedbackStore()


@pytest.fixture
def dashboard(mock_service, feedback_store):
    return MonitoringDashboard(
        evolution_service=mock_service,
        host="localhost",
        port=18092,
        auth_token=None,
        feedback_store=feedback_store,
    )


@pytest.fixture
def auth_dashboard(mock_service, feedback_store):
    return MonitoringDashboard(
        evolution_service=mock_service,
        host="localhost",
        port=18093,
        auth_token="test-token",
        feedback_store=feedback_store,
    )


async def _get(app, path, **kwargs):
    import aiohttp

    async with TestServer(app) as server:
        url = f"http://localhost:{server.port}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, **kwargs) as resp:
                body = await resp.text()
                return resp.status, body


async def _post(app, path, json=None, **kwargs):
    import aiohttp

    async with TestServer(app) as server:
        url = f"http://localhost:{server.port}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=json, **kwargs) as resp:
                body = await resp.text()
                return resp.status, body


class TestFeedbackPendingEndpoint:
    @pytest.mark.asyncio
    async def test_empty_pending(self, dashboard):
        status, body = await _get(dashboard.app, "/api/feedback/pending")
        assert status == 200
        import json

        assert json.loads(body) == []

    @pytest.mark.asyncio
    async def test_returns_pending_proposals(self, dashboard, feedback_store):
        feedback_store.submit_proposal("Fix bug", "desc")
        status, body = await _get(dashboard.app, "/api/feedback/pending")
        assert status == 200
        import json

        data = json.loads(body)
        assert len(data) == 1
        assert data[0]["title"] == "Fix bug"
        assert data[0]["decision"] == "pending"

    @pytest.mark.asyncio
    async def test_excludes_decided(self, dashboard, feedback_store):
        p = feedback_store.submit_proposal("A", "a")
        feedback_store.approve(p.id)
        status, body = await _get(dashboard.app, "/api/feedback/pending")
        import json

        assert json.loads(body) == []


class TestFeedbackApproveEndpoint:
    @pytest.mark.asyncio
    async def test_approve_success(self, dashboard, feedback_store):
        p = feedback_store.submit_proposal("Fix bug", "desc")
        status, body = await _post(
            dashboard.app,
            f"/api/feedback/{p.id}/approve",
            json={"decided_by": "alice", "reason": "good"},
        )
        assert status == 200
        import json

        data = json.loads(body)
        assert data["decision"] == "approved"
        assert data["decided_by"] == "alice"

    @pytest.mark.asyncio
    async def test_approve_nonexistent(self, dashboard):
        status, _ = await _post(dashboard.app, "/api/feedback/nonexistent/approve")
        assert status == 404

    @pytest.mark.asyncio
    async def test_approve_already_decided(self, dashboard, feedback_store):
        p = feedback_store.submit_proposal("T", "D")
        feedback_store.approve(p.id)
        status, _ = await _post(dashboard.app, f"/api/feedback/{p.id}/approve")
        assert status == 404

    @pytest.mark.asyncio
    async def test_approve_malformed_json(self, dashboard, feedback_store):
        """Malformed JSON body should return 400, not 500."""
        import aiohttp

        p = feedback_store.submit_proposal("T", "D")
        async with TestServer(dashboard.app) as server:
            url = f"http://localhost:{server.port}/api/feedback/{p.id}/approve"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data="not json",
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    assert resp.status == 400
                    body = await resp.json()
                    assert "Invalid JSON" in body["error"]

    @pytest.mark.asyncio
    async def test_approve_null_decided_by_coalesces(self, dashboard, feedback_store):
        """A null decided_by should fall back to 'operator', not store None."""
        p = feedback_store.submit_proposal("T", "D")
        status, body = await _post(
            dashboard.app,
            f"/api/feedback/{p.id}/approve",
            json={"decided_by": None},
        )
        assert status == 200
        import json

        data = json.loads(body)
        assert data["decided_by"] == "operator"


class TestFeedbackRejectEndpoint:
    @pytest.mark.asyncio
    async def test_reject_success(self, dashboard, feedback_store):
        p = feedback_store.submit_proposal("Fix bug", "desc")
        status, body = await _post(
            dashboard.app,
            f"/api/feedback/{p.id}/reject",
            json={"decided_by": "bob", "reason": "too risky"},
        )
        assert status == 200
        import json

        data = json.loads(body)
        assert data["decision"] == "rejected"
        assert data["reason"] == "too risky"

    @pytest.mark.asyncio
    async def test_reject_nonexistent(self, dashboard):
        status, _ = await _post(dashboard.app, "/api/feedback/nonexistent/reject")
        assert status == 404

    @pytest.mark.asyncio
    async def test_reject_malformed_json(self, dashboard, feedback_store):
        """Malformed JSON body should return 400, not 500."""
        import aiohttp

        p = feedback_store.submit_proposal("T", "D")
        async with TestServer(dashboard.app) as server:
            url = f"http://localhost:{server.port}/api/feedback/{p.id}/reject"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data="not json",
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    assert resp.status == 400
                    body = await resp.json()
                    assert "Invalid JSON" in body["error"]

    @pytest.mark.asyncio
    async def test_reject_null_decided_by_coalesces(self, dashboard, feedback_store):
        """A null decided_by should fall back to 'operator', not store None."""
        p = feedback_store.submit_proposal("T", "D")
        status, body = await _post(
            dashboard.app,
            f"/api/feedback/{p.id}/reject",
            json={"decided_by": None},
        )
        assert status == 200
        import json

        data = json.loads(body)
        assert data["decided_by"] == "operator"


class TestFeedbackStatsEndpoint:
    @pytest.mark.asyncio
    async def test_empty_stats(self, dashboard):
        status, body = await _get(dashboard.app, "/api/feedback/stats")
        assert status == 200
        import json

        data = json.loads(body)
        assert data["total"] == 0
        assert data["acceptance_rate"] is None

    @pytest.mark.asyncio
    async def test_stats_with_decisions(self, dashboard, feedback_store):
        p1 = feedback_store.submit_proposal("A", "a")
        p2 = feedback_store.submit_proposal("B", "b")
        feedback_store.approve(p1.id)
        feedback_store.reject(p2.id)
        status, body = await _get(dashboard.app, "/api/feedback/stats")
        import json

        data = json.loads(body)
        assert data["total"] == 2
        assert data["approved"] == 1
        assert data["rejected"] == 1
        assert data["acceptance_rate"] == 50.0


class TestFeedbackAuth:
    @pytest.mark.asyncio
    async def test_pending_requires_auth(self, auth_dashboard):
        status, _ = await _get(auth_dashboard.app, "/api/feedback/pending")
        assert status == 401

    @pytest.mark.asyncio
    async def test_pending_with_auth(self, auth_dashboard):
        status, _ = await _get(
            auth_dashboard.app,
            "/api/feedback/pending",
            headers={"Authorization": "Bearer test-token"},
        )
        assert status == 200

    @pytest.mark.asyncio
    async def test_approve_requires_auth(self, auth_dashboard, feedback_store):
        p = feedback_store.submit_proposal("T", "D")
        status, _ = await _post(auth_dashboard.app, f"/api/feedback/{p.id}/approve")
        assert status == 401

    @pytest.mark.asyncio
    async def test_stats_requires_auth(self, auth_dashboard):
        status, _ = await _get(auth_dashboard.app, "/api/feedback/stats")
        assert status == 401
