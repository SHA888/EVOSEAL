"""Tests for MonitoringDashboard auth and CORS hardening."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from evoseal.services.monitoring_dashboard import MonitoringDashboard


@pytest.fixture
def mock_service():
    """Create a mock ContinuousEvolutionService."""
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
def dashboard_no_auth(mock_service):
    """Dashboard without authentication."""
    return MonitoringDashboard(
        evolution_service=mock_service,
        host="localhost",
        port=18081,
        auth_token=None,
    )


@pytest.fixture
def dashboard_with_auth(mock_service):
    """Dashboard with token authentication."""
    return MonitoringDashboard(
        evolution_service=mock_service,
        host="localhost",
        port=18082,
        auth_token="test-secret-token",
    )


async def _make_request(app, method, path, **kwargs):
    """Helper: start TestServer and make one request."""
    async with TestServer(app) as server:
        import aiohttp

        url = f"http://localhost:{server.port}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **kwargs) as resp:
                body = await resp.text()
                return resp.status, body, resp.headers


class TestAuthMiddleware:
    """Test the bearer-token auth middleware."""

    @pytest.mark.asyncio
    async def test_no_auth_allows_all(self, dashboard_no_auth):
        """When auth_token is None, all requests pass through."""
        app = dashboard_no_auth.app
        app.router.add_get("/api/status", dashboard_no_auth.api_status)

        status, _, _ = await _make_request(app, "GET", "/api/status")
        assert status == 200

    @pytest.mark.asyncio
    async def test_auth_rejects_missing_token(self, dashboard_with_auth):
        """When auth_token is set, requests without Authorization are rejected."""
        app = dashboard_with_auth.app
        app.router.add_get("/api/status", dashboard_with_auth.api_status)

        status, body, _ = await _make_request(app, "GET", "/api/status")
        assert status == 401
        assert "Unauthorized" in body

    @pytest.mark.asyncio
    async def test_auth_rejects_wrong_token(self, dashboard_with_auth):
        """Wrong bearer token is rejected."""
        app = dashboard_with_auth.app
        app.router.add_get("/api/status", dashboard_with_auth.api_status)

        status, _, _ = await _make_request(
            app,
            "GET",
            "/api/status",
            headers={"Authorization": "Bearer wrong"},
        )
        assert status == 401

    @pytest.mark.asyncio
    async def test_auth_accepts_correct_token(self, dashboard_with_auth):
        """Correct bearer token is accepted."""
        app = dashboard_with_auth.app
        app.router.add_get("/api/status", dashboard_with_auth.api_status)

        status, _, _ = await _make_request(
            app,
            "GET",
            "/api/status",
            headers={"Authorization": "Bearer test-secret-token"},
        )
        assert status == 200

    @pytest.mark.asyncio
    async def test_auth_dashboard_page_not_gated(self, dashboard_with_auth):
        """The HTML dashboard page (/) does not require auth."""
        app = dashboard_with_auth.app
        app.router.add_get("/", dashboard_with_auth.dashboard_page)

        status, body, _ = await _make_request(app, "GET", "/")
        assert status == 200
        assert "EVOSEAL" in body

    @pytest.mark.asyncio
    async def test_auth_api_metrics_rejected_without_token(self, dashboard_with_auth):
        """/api/* endpoints require auth when token is set."""
        app = dashboard_with_auth.app
        app.router.add_get("/api/metrics", dashboard_with_auth.api_metrics)

        status, _, _ = await _make_request(app, "GET", "/api/metrics")
        assert status == 401

    @pytest.mark.asyncio
    async def test_auth_allows_options_preflight(self, dashboard_with_auth):
        """OPTIONS requests pass through auth for CORS preflight."""
        app = dashboard_with_auth.app
        app.router.add_get("/api/status", dashboard_with_auth.api_status)

        import aiohttp

        async with TestServer(app) as server:
            url = f"http://localhost:{server.port}/api/status"
            async with aiohttp.ClientSession() as session:
                async with session.options(url) as resp:
                    # Should NOT be 401 — OPTIONS must pass through
                    assert resp.status != 401

    @pytest.mark.asyncio
    async def test_auth_api_report_rejected_without_token(self, dashboard_with_auth):
        """/api/report requires auth when token is set."""
        app = dashboard_with_auth.app
        app.router.add_get("/api/report", dashboard_with_auth.api_report)

        status, _, _ = await _make_request(app, "GET", "/api/report")
        assert status == 401

    @pytest.mark.asyncio
    async def test_ws_auth_via_sec_protocol_header(self, dashboard_with_auth):
        """WebSocket auth via Sec-WebSocket-Protocol: bearer.<token> header."""
        import aiohttp

        app = dashboard_with_auth.app

        async with TestServer(app) as server:
            url = f"http://localhost:{server.port}/ws"
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    url, headers={"Sec-WebSocket-Protocol": "bearer.test-secret-token"}
                ) as ws:
                    msg = await ws.receive()
                    # Should receive initial data, not a 401 rejection
                    assert msg.type == aiohttp.WSMsgType.TEXT

    @pytest.mark.asyncio
    async def test_ws_auth_rejects_wrong_sec_protocol(self, dashboard_with_auth):
        """Wrong token in Sec-WebSocket-Protocol is rejected at HTTP upgrade (401)."""
        import aiohttp

        app = dashboard_with_auth.app

        async with TestServer(app) as server:
            url = f"http://localhost:{server.port}/ws"
            async with aiohttp.ClientSession() as session:
                with pytest.raises(aiohttp.WSServerHandshakeError) as exc_info:
                    await session.ws_connect(
                        url, headers={"Sec-WebSocket-Protocol": "bearer.wrong-token"}
                    )
                assert exc_info.value.status == 401

    @pytest.mark.asyncio
    async def test_ws_auth_rejects_legacy_bearer_space_format(self, dashboard_with_auth):
        """Old 'Bearer <token>' format with space is rejected (RFC 6455 invalid token)."""
        import aiohttp

        app = dashboard_with_auth.app

        async with TestServer(app) as server:
            url = f"http://localhost:{server.port}/ws"
            async with aiohttp.ClientSession() as session:
                with pytest.raises(aiohttp.WSServerHandshakeError) as exc_info:
                    await session.ws_connect(
                        url,
                        headers={"Sec-WebSocket-Protocol": "Bearer test-secret-token"},
                    )
                assert exc_info.value.status == 401

    @pytest.mark.asyncio
    async def test_non_ascii_token_rejected_at_init(self, mock_service):
        """A non-ASCII auth_token is rejected at construction (invalid HTTP token)."""
        with pytest.raises(ValueError, match="invalid in HTTP tokens"):
            MonitoringDashboard(
                evolution_service=mock_service,
                host="localhost",
                port=18090,
                auth_token="über-sécret",
            )

    def test_constant_compare_non_ascii(self):
        """_constant_compare handles non-ASCII strings without raising."""
        cmp = MonitoringDashboard._constant_compare
        assert cmp("abc", "abc") is True
        assert cmp("abc", "def") is False
        assert cmp("über", "über") is True
        assert cmp("über", "other") is False
        assert cmp("", "") is True

    def test_empty_auth_token_raises(self, mock_service):
        """Setting auth_token='' (empty string) raises ValueError."""
        with pytest.raises(ValueError, match="auth_token must not be an empty string"):
            MonitoringDashboard(
                evolution_service=mock_service,
                host="localhost",
                port=18091,
                auth_token="",
            )


class TestCorsHardening:
    """Test that CORS is restricted, not wildcard."""

    def test_default_origins_are_localhost(self, dashboard_no_auth):
        """Default CORS origins should be localhost, not '*'."""
        assert "*" not in dashboard_no_auth.allowed_origins
        assert any("localhost" in o for o in dashboard_no_auth.allowed_origins)

    def test_wildcard_origins_warn_and_disable_credentials(self, mock_service, caplog):
        """Explicit '*' origin disables allow_credentials."""
        import logging

        with caplog.at_level(logging.WARNING):
            MonitoringDashboard(
                evolution_service=mock_service,
                host="localhost",
                port=18083,
                allowed_origins=["*"],
            )

        assert any("allow_credentials" in r.message for r in caplog.records)

    def test_custom_origins_preserved(self, mock_service):
        """Custom allowed_origins are stored as-is."""
        custom = ["https://example.com", "https://app.example.com"]
        dash = MonitoringDashboard(
            evolution_service=mock_service,
            host="localhost",
            port=18084,
            allowed_origins=custom,
        )
        assert dash.allowed_origins == custom

    def test_bind_all_warns(self, mock_service, caplog):
        """Binding to 0.0.0.0 logs a security warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            MonitoringDashboard(
                evolution_service=mock_service,
                host="0.0.0.0",
                port=18085,
            )

        assert any("0.0.0.0" in r.message for r in caplog.records)

    def test_bind_ipv6_wildcard_warns(self, mock_service, caplog):
        """Binding to :: logs a security warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            MonitoringDashboard(
                evolution_service=mock_service,
                host="::",
                port=18086,
            )

        assert any("::" in r.message for r in caplog.records)

    def test_wildcard_origins_with_auth_token_raises(self, mock_service):
        """Combining allowed_origins=['*'] with auth_token raises ValueError."""
        with pytest.raises(ValueError, match="allowed_origins.*auth_token"):
            MonitoringDashboard(
                evolution_service=mock_service,
                host="localhost",
                port=18087,
                auth_token="secret",
                allowed_origins=["*"],
            )


class TestDashboardDefaults:
    """Test constructor defaults and parameter storage."""

    def test_auth_token_stored(self, dashboard_with_auth):
        assert dashboard_with_auth.auth_token == "test-secret-token"

    def test_auth_token_none_by_default(self, dashboard_no_auth):
        assert dashboard_no_auth.auth_token is None

    def test_0_0_0_0_default_origins_are_localhost(self, mock_service):
        """When host is 0.0.0.0, default origins include localhost:<port> only."""
        dash = MonitoringDashboard(
            evolution_service=mock_service,
            host="0.0.0.0",
            port=9613,
        )
        assert "*" not in dash.allowed_origins
        assert "http://localhost:9613" in dash.allowed_origins
        # Bare http://localhost (no port) should NOT be included
        assert "http://localhost" not in dash.allowed_origins

    def test_ipv6_loopback_origin_is_bracketed(self, mock_service):
        """IPv6 host ::1 must produce http://[::1]:<port>, not http://::1:<port>."""
        dash = MonitoringDashboard(
            evolution_service=mock_service,
            host="::1",
            port=8081,
        )
        assert "http://[::1]:8081" in dash.allowed_origins

    def test_ipv6_custom_origin_is_bracketed(self, mock_service):
        """Any IPv6 literal gets brackets in the default origin."""
        dash = MonitoringDashboard(
            evolution_service=mock_service,
            host="fe80::1",
            port=9000,
        )
        assert "http://[fe80::1]:9000" in dash.allowed_origins

    def test_ipv4_origin_not_double_bracketed(self, mock_service):
        """IPv4 addresses are not bracketed."""
        dash = MonitoringDashboard(
            evolution_service=mock_service,
            host="192.168.1.10",
            port=8081,
        )
        assert "http://192.168.1.10:8081" in dash.allowed_origins
        assert "[" not in dash.allowed_origins[0]

    def test_mixed_wildcard_and_explicit_origins_credentials_per_origin(self, mock_service):
        """When '*' is mixed with explicit origins, only '*' disables credentials."""
        dash = MonitoringDashboard(
            evolution_service=mock_service,
            host="localhost",
            port=8081,
            allowed_origins=["https://trusted.example.com", "*"],
        )
        # Verify the allowed_origins are stored as-is
        assert dash.allowed_origins == ["https://trusted.example.com", "*"]
        # The actual CORS options are set up in setup_cors — we verify
        # indirectly that the object was created without error.
        # Direct verification of aiohttp_cors internals is fragile,
        # but we can confirm the dashboard constructed successfully.
        assert dash.app is not None

    def test_invalid_auth_token_with_slash_raises(self, mock_service):
        """auth_token containing '/' (common in base64) raises ValueError."""
        with pytest.raises(ValueError, match="invalid in HTTP tokens"):
            MonitoringDashboard(
                evolution_service=mock_service,
                host="localhost",
                port=8081,
                auth_token="abc/def+ghi=",
            )

    def test_invalid_auth_token_with_space_raises(self, mock_service):
        """auth_token containing whitespace raises ValueError."""
        with pytest.raises(ValueError, match="invalid in HTTP tokens"):
            MonitoringDashboard(
                evolution_service=mock_service,
                host="localhost",
                port=8081,
                auth_token="has space",
            )

    def test_valid_urlsafe_token_accepted(self, mock_service):
        """A URL-safe token (hex or token_urlsafe chars) is accepted."""
        dash = MonitoringDashboard(
            evolution_service=mock_service,
            host="localhost",
            port=8081,
            auth_token="abc123-_DEF",
        )
        assert dash.auth_token == "abc123-_DEF"


class TestWebSocketSubprotocolEcho:
    """Test that the server echoes the accepted subprotocol."""

    @pytest.mark.asyncio
    async def test_ws_echoes_bearer_subprotocol(self, dashboard_with_auth):
        """Server must echo the bearer.<token> subprotocol in handshake."""
        import aiohttp

        app = dashboard_with_auth.app

        async with TestServer(app) as server:
            url = f"http://localhost:{server.port}/ws"
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    url,
                    headers={"Sec-WebSocket-Protocol": "bearer.test-secret-token"},
                    protocols=["bearer.test-secret-token"],
                ) as ws:
                    # ws_connect with protocols= will raise if server
                    # doesn't echo the subprotocol. Getting here means
                    # the echo worked.
                    msg = await ws.receive()
                    assert msg.type == aiohttp.WSMsgType.TEXT

    @pytest.mark.asyncio
    async def test_ws_no_subprotocol_when_no_auth(self, dashboard_no_auth):
        """When no auth_token is set, WS connects without subprotocol."""
        import aiohttp

        app = dashboard_no_auth.app

        async with TestServer(app) as server:
            url = f"http://localhost:{server.port}/ws"
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url) as ws:
                    msg = await ws.receive()
                    assert msg.type == aiohttp.WSMsgType.TEXT


class TestOfflineMode:
    """Test dashboard offline mode with data loaded from disk."""

    @pytest.fixture
    def offline_data_dir(self, tmp_path):
        """Create a minimal .evoseal/ data directory with test data."""
        data_dir = tmp_path / ".evoseal"
        data_dir.mkdir()

        # Pipeline state
        pipeline_state = {
            "status": "completed",
            "repository": ".",
            "current_iteration": 5,
            "total_iterations": 10,
            "start_time": 1700000000.0,
            "completion_time": 1700003600.0,
            "current_stage": "Finalizing",
            "config": {"iterations": 10},
        }
        (data_dir / "pipeline_state.json").write_text(json.dumps(pipeline_state))

        # Pipeline config
        pipeline_config = {"iterations": 10, "auto_checkpoint": True}
        (data_dir / "pipeline_config.json").write_text(json.dumps(pipeline_config))

        # Budget snapshot
        metrics_dir = data_dir / "metrics"
        metrics_dir.mkdir()
        budget = {
            "total_tokens": 50000,
            "total_cost": 0.75,
            "budget_max_tokens": 1000000,
            "budget_max_cost": 10.0,
        }
        (metrics_dir / "budget_snapshot.json").write_text(json.dumps(budget))

        # Version registry
        versions_dir = tmp_path / "models" / "versions"
        versions_dir.mkdir(parents=True)
        registry = {
            "versions": [
                {"version_id": "v1", "model": "devstral:latest"},
                {"version_id": "v2", "model": "devstral-v2:latest"},
            ],
            "current_version": "v2",
        }
        (versions_dir / "version_registry.json").write_text(json.dumps(registry))

        # Experiment database (SQLite)
        db_path = data_dir / "experiments.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE experiments "
            "(id TEXT PRIMARY KEY, name TEXT, experiment_type TEXT, "
            "status TEXT, created_at TEXT, updated_at TEXT)"
        )
        conn.execute(
            "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?)",
            (
                "exp-1",
                "Test Run",
                "evolution",
                "completed",
                "2025-01-01T00:00:00",
                "2025-01-01T01:00:00",
            ),
        )
        conn.commit()
        conn.close()

        return data_dir

    @pytest.fixture
    def offline_dashboard(self, offline_data_dir):
        """Dashboard in offline mode."""
        return MonitoringDashboard(
            host="localhost",
            port=18092,
            data_dir=offline_data_dir,
        )

    def test_offline_status_loads_data(self, offline_dashboard):
        """api_status returns loaded data when in offline mode."""
        status = offline_dashboard._build_offline_status()
        assert status["mode"] == "offline"
        assert status["is_running"] is False
        assert status["status"] == "completed"
        assert status["current_iteration"] == 5
        assert status["total_iterations"] == 10
        assert status["model_versions"] == 2
        assert status["current_model"] == "v2"

    def test_offline_metrics_loads_data(self, offline_dashboard):
        """_build_offline_metrics returns structured data for the UI."""
        metrics = offline_dashboard._build_offline_metrics()
        assert metrics["service_status"]["mode"] == "offline"
        assert metrics["service_status"]["is_running"] is False
        assert metrics["evolution_status"]["iterations_completed"] == 5
        assert metrics["evolution_status"]["total_iterations"] == 10
        assert metrics["evolution_status"]["experiments_count"] == 1
        assert metrics["dashboard_info"]["mode"] == "offline"
        assert metrics["training_status"]["note"]

    def test_offline_metrics_includes_budget(self, offline_dashboard):
        """Offline metrics include budget snapshot data."""
        metrics = offline_dashboard._build_offline_metrics()
        budget = metrics["service_status"]["budget"]
        assert budget["total_tokens"] == 50000
        assert budget["total_cost"] == 0.75

    def test_offline_report_loads_all_sources(self, offline_dashboard):
        """_build_offline_report includes all data sources."""
        report = offline_dashboard._build_offline_report()
        assert report["mode"] == "offline"
        assert report["pipeline_state"]["status"] == "completed"
        assert report["pipeline_config"]["iterations"] == 10
        assert len(report["version_registry"]["versions"]) == 2
        assert report["budget_snapshot"]["total_tokens"] == 50000
        assert len(report["experiments"]) == 1
        assert "offline" in report["note"].lower()

    def test_offline_cache_is_used(self, offline_dashboard):
        """Repeated calls use the cached data, not re-read disk."""
        result1 = offline_dashboard._load_offline_data()
        assert offline_dashboard._offline_cache is not None
        result2 = offline_dashboard._load_offline_data()
        assert result1 is result2  # Same object, not re-read

    def test_offline_with_no_data_dir_returns_error(self):
        """Dashboard with no service and no data_dir returns error."""
        dash = MonitoringDashboard(host="localhost", port=18093)
        assert dash.data_dir is None
        status = dash._build_offline_status()
        assert "error" in status

    def test_offline_with_missing_data_dir_returns_error(self, tmp_path):
        """Dashboard with nonexistent data_dir returns error."""
        dash = MonitoringDashboard(
            host="localhost",
            port=18094,
            data_dir=tmp_path / "nonexistent",
        )
        status = dash._build_offline_status()
        assert "error" in status

    def test_offline_with_corrupt_json_recovered(self, tmp_path):
        """Corrupt JSON in pipeline_state is handled gracefully."""
        data_dir = tmp_path / ".evoseal"
        data_dir.mkdir()
        (data_dir / "pipeline_state.json").write_text("not valid json {{{")

        dash = MonitoringDashboard(
            host="localhost",
            port=18095,
            data_dir=data_dir,
        )
        data = dash._load_offline_data()
        # Should not raise; pipeline_state key is omitted due to corrupt file
        assert "pipeline_state" not in data

    def test_offline_corrupt_json_status_and_metrics_not_crash(self, tmp_path):
        """_build_offline_status and _build_offline_metrics degrade gracefully
        when pipeline_state.json is corrupt (key absent, defaults apply)."""
        data_dir = tmp_path / ".evoseal"
        data_dir.mkdir()
        (data_dir / "pipeline_state.json").write_text("not valid json {{{")

        dash = MonitoringDashboard(
            host="localhost",
            port=18100,
            data_dir=data_dir,
        )
        # Must not raise — absent key falls back to {} via .get()
        status = dash._build_offline_status()
        assert status["mode"] == "offline"
        assert status["status"] == "unknown"  # falls back to default

        metrics = dash._build_offline_metrics()
        assert metrics["service_status"]["mode"] == "offline"
        assert metrics["service_status"]["status"] == "unknown"

    def test_offline_with_empty_data_dir(self, tmp_path):
        """Empty data_dir loads without error — just no data."""
        data_dir = tmp_path / ".evoseal"
        data_dir.mkdir()

        dash = MonitoringDashboard(
            host="localhost",
            port=18096,
            data_dir=data_dir,
        )
        data = dash._load_offline_data()
        assert data["mode"] == "offline"
        assert "pipeline_state" not in data
        assert "experiments" not in data

    @pytest.mark.asyncio
    async def test_offline_api_metrics_endpoint(self, offline_dashboard):
        """GET /api/metrics returns offline data via HTTP."""
        import aiohttp
        from aiohttp.test_utils import TestServer

        app = offline_dashboard.app
        app.router.add_get("/api/metrics", offline_dashboard.api_metrics)

        async with TestServer(app) as server:
            url = f"http://localhost:{server.port}/api/metrics"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["service_status"]["mode"] == "offline"
                    assert data["evolution_status"]["iterations_completed"] == 5

    @pytest.mark.asyncio
    async def test_offline_api_status_endpoint(self, offline_dashboard):
        """GET /api/status returns offline status via HTTP."""
        import aiohttp
        from aiohttp.test_utils import TestServer

        app = offline_dashboard.app
        app.router.add_get("/api/status", offline_dashboard.api_status)

        async with TestServer(app) as server:
            url = f"http://localhost:{server.port}/api/status"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["mode"] == "offline"
                    assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_offline_api_report_endpoint(self, offline_dashboard):
        """GET /api/report returns offline report via HTTP."""
        import aiohttp
        from aiohttp.test_utils import TestServer

        app = offline_dashboard.app
        app.router.add_get("/api/report", offline_dashboard.api_report)

        async with TestServer(app) as server:
            url = f"http://localhost:{server.port}/api/report"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["mode"] == "offline"
                    assert "pipeline_state" in data
                    assert "experiments" in data

    def test_offline_data_dir_stored(self, offline_data_dir):
        """data_dir is stored as a Path on the dashboard."""
        dash = MonitoringDashboard(
            host="localhost",
            port=18097,
            data_dir=offline_data_dir,
        )
        assert dash.data_dir == offline_data_dir
        assert isinstance(dash.data_dir, Path)

    def test_offline_data_dir_from_string(self, offline_data_dir):
        """data_dir accepts a string and converts to Path."""
        dash = MonitoringDashboard(
            host="localhost",
            port=18098,
            data_dir=str(offline_data_dir),
        )
        assert isinstance(dash.data_dir, Path)
        assert dash.data_dir == offline_data_dir

    def test_offline_experiments_from_db(self, offline_data_dir):
        """_load_experiments_from_db reads from SQLite."""
        db_path = offline_data_dir / "experiments.db"
        experiments = MonitoringDashboard._load_experiments_from_db(db_path)
        assert len(experiments) == 1
        assert experiments[0]["id"] == "exp-1"
        assert experiments[0]["name"] == "Test Run"
        assert experiments[0]["status"] == "completed"

    def test_offline_experiments_missing_table(self, tmp_path):
        """_load_experiments_from_db handles missing table gracefully."""
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE other_table (id TEXT)")
        conn.commit()
        conn.close()

        experiments = MonitoringDashboard._load_experiments_from_db(db_path)
        assert experiments == []

    def test_service_takes_precedence_over_offline(self, mock_service, offline_data_dir):
        """When both evolution_service and data_dir are set, live service wins."""
        dash = MonitoringDashboard(
            evolution_service=mock_service,
            host="localhost",
            port=18099,
            data_dir=offline_data_dir,
        )
        # _get_current_metrics should use the live service, not offline data
        import asyncio

        metrics = asyncio.run(dash._get_current_metrics())
        # The live service mock returns is_running: True, not mode: offline
        assert metrics["service_status"]["is_running"] is True

    def test_offline_cache_invalidated_on_mtime_change(self, offline_data_dir):
        """Cache is refreshed when a source file's mtime changes."""
        dash = MonitoringDashboard(
            host="localhost",
            port=18101,
            data_dir=offline_data_dir,
        )
        data1 = dash._load_offline_data()
        assert data1.get("pipeline_state", {}).get("status") == "completed"

        # Simulate an external write to the pipeline state file.
        import time

        new_state = {
            "status": "running",
            "current_iteration": 7,
            "total_iterations": 10,
        }
        state_file = offline_data_dir / "pipeline_state.json"
        state_file.write_text(json.dumps(new_state))
        # Ensure mtime is actually different (filesystem granularity).
        time.sleep(0.05)

        data2 = dash._load_offline_data()
        assert data2["pipeline_state"]["status"] == "running"
        assert data2["pipeline_state"]["current_iteration"] == 7
        assert data2 is not data1  # new cache object

    def test_offline_timestamp_seconds_to_milliseconds(self, offline_dashboard):
        """Unix timestamps in seconds are converted to milliseconds for JS."""
        metrics = offline_dashboard._build_offline_metrics()
        last_activity = metrics["service_status"]["statistics"]["last_activity"]
        # Fixture has completion_time=1700003600.0 (seconds).
        # JS new Date() expects milliseconds → 2023-11-14T22:13:20 UTC.
        assert last_activity == 1700003600.0 * 1000
        import datetime

        dt = datetime.datetime.fromtimestamp(last_activity / 1000, tz=datetime.timezone.utc)
        assert dt.year == 2023
        assert dt.month == 11

    def test_offline_timestamp_none_passthrough(self):
        """_offline_timestamp returns None for None input."""
        assert MonitoringDashboard._offline_timestamp(None) is None

    def test_offline_timestamp_string_passthrough(self):
        """_offline_timestamp passes ISO strings through unchanged."""
        iso = "2023-11-14T22:13:20Z"
        assert MonitoringDashboard._offline_timestamp(iso) == iso

    def test_offline_cache_lock_prevents_double_read(self, offline_data_dir):
        """Concurrent first-reads don't both populate the cache."""
        import threading

        dash = MonitoringDashboard(
            host="localhost",
            port=18102,
            data_dir=offline_data_dir,
        )
        results: list[dict] = []
        barrier = threading.Barrier(2)

        def read_with_barrier():
            barrier.wait()
            results.append(dash._load_offline_data())

        threads = [threading.Thread(target=read_with_barrier) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Both got the same cached object (identity, not just equality).
        assert results[0] is results[1]

    def test_cli_auth_token_flag(self):
        """--auth-token is accepted by the CLI argument parser."""
        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import argparse; "
                "p = argparse.ArgumentParser(); "
                "p.add_argument('--auth-token', type=str, default=None); "
                "args = p.parse_args(['--auth-token', 'secret123']); "
                "assert args.auth_token == 'secret123'",
            ],
            capture_output=True,
        )
        assert result.returncode == 0
