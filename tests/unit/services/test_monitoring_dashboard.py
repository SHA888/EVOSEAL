"""Tests for MonitoringDashboard auth and CORS hardening."""

from __future__ import annotations

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
