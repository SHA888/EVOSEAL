"""
Web-based monitoring dashboard for EVOSEAL continuous evolution.

This module provides a real-time dashboard for monitoring the bidirectional
evolution system, displaying metrics, progress, and system health.
"""

import asyncio
import hmac
import ipaddress
import json
import logging
import re
import weakref
from datetime import datetime
from typing import Any

import aiohttp_cors
from aiohttp import WSMsgType, web

from .continuous_evolution_service import ContinuousEvolutionService

logger = logging.getLogger(__name__)

# RFC 7230 §3.2.6 — token characters (tchar) plus the subset safe for
# WebSocket subprotocol strings (RFC 6455 §4.2.1).
_HTTP_TOKEN_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


def _is_http_token(value: str) -> bool:
    """Return True if *value* is a valid HTTP token (RFC 7230 §3.2.6)."""
    return bool(_HTTP_TOKEN_RE.match(value))


def _bracket_ipv6(host: str) -> str:
    """Wrap bare IPv6 literals in brackets for use in URLs."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return host
    if addr.version == 6:
        return f"[{host}]"
    return host


class MonitoringDashboard:
    """
    Web-based monitoring dashboard for continuous evolution.

    Provides real-time monitoring of evolution progress, training cycles,
    model improvements, and system health through a web interface.
    """

    def __init__(
        self,
        evolution_service: ContinuousEvolutionService | None = None,
        host: str = "localhost",
        port: int = 8081,
        update_interval: int = 30,
        auth_token: str | None = None,
        allowed_origins: list[str] | None = None,
    ):
        """
        Initialize the monitoring dashboard.

        Args:
            evolution_service: The continuous evolution service to monitor
            host: Dashboard host address
            port: Dashboard port
            update_interval: Seconds between dashboard updates
            auth_token: Optional bearer token for API/WebSocket auth.
                When set, all /api/* and /ws requests must include
                Authorization: Bearer <token>. The dashboard HTML page is
                not gated (it only loads the JS client).
            allowed_origins: Origins allowed for CORS. Defaults to the
                dashboard's own origin(s) using http://. If the dashboard
                is behind TLS termination or accessed via a different
                hostname than the bind host, pass the correct origins
                explicitly. Pass ["*"] explicitly to allow all origins
                (raises ValueError when combined with auth_token).
        """
        self.evolution_service = evolution_service
        self.host = host
        self.port = port
        self.update_interval = update_interval
        self.auth_token = auth_token

        if auth_token is not None and auth_token == "":
            raise ValueError(
                "auth_token must not be an empty string. "
                "Set auth_token=None to disable authentication."
            )

        if auth_token is not None and not _is_http_token(auth_token):
            raise ValueError(
                "auth_token contains characters that are invalid in HTTP "
                "tokens (RFC 7230 §3.2.6) and WebSocket subprotocol "
                "strings (RFC 6455 §4.2.1). Characters like '/', '=', "
                "and whitespace will break the bearer.<token> subprotocol "
                "auth path. Use secrets.token_urlsafe() or hex for "
                "token generation."
            )

        if host in ("0.0.0.0", "::"):
            logger.warning(
                "Dashboard is bound to %s — accessible from any network "
                "interface. Ensure auth_token is set or restrict access via firewall.",
                host,
            )

        # Build default CORS origins from host/port
        if allowed_origins is None:
            if host in ("0.0.0.0", "::"):
                allowed_origins = [f"http://localhost:{port}"]
            else:
                allowed_origins = [f"http://{_bracket_ipv6(host)}:{port}"]
        self.allowed_origins = allowed_origins

        if self.auth_token and "*" in self.allowed_origins:
            raise ValueError(
                "allowed_origins=['*'] combined with auth_token is insecure — "
                "any origin can make authenticated requests. "
                "Restrict allowed_origins to trusted origins."
            )

        # Web application
        self.app = web.Application(middlewares=[self._auth_middleware])
        self.setup_routes()
        self.setup_cors()

        # WebSocket connections for real-time updates
        self.websockets = weakref.WeakSet()

        # Dashboard state
        self.is_running = False
        self.update_task = None

        logger.info(f"MonitoringDashboard initialized on {host}:{port}")

    def setup_routes(self):
        """Setup web application routes."""
        self.app.router.add_get("/", self.dashboard_page)
        self.app.router.add_get("/api/status", self.api_status)
        self.app.router.add_get("/api/metrics", self.api_metrics)
        self.app.router.add_get("/api/report", self.api_report)
        self.app.router.add_get("/api/generation-diffs", self.api_generation_diffs)
        self.app.router.add_get("/ws", self.websocket_handler)
        # Static files embedded in HTML, no separate static directory needed

    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler):
        """Reject unauthenticated API/WebSocket requests when auth_token is set."""
        if self.auth_token and request.path != "/":
            # Let CORS preflight through — aiohttp_cors handles these.
            if request.method == "OPTIONS":
                return await handler(request)
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {self.auth_token}"
            if self._constant_compare(auth_header, expected):
                pass
            elif request.path == "/ws":
                # Preferred: Sec-WebSocket-Protocol header (token not in URL/logs).
                # Fallback: ?token= query param (logged in access/proxy logs —
                # only use when the client cannot set headers, e.g. browser JS
                # without Sec-WebSocket-Protocol support).
                ws_protocols = request.headers.get("Sec-WebSocket-Protocol", "")
                token_from_protocol = ""
                for proto in ws_protocols.split(","):
                    proto = proto.strip()
                    if proto.startswith("bearer."):
                        token_from_protocol = proto[7:]
                        break
                if token_from_protocol and self._constant_compare(
                    token_from_protocol, self.auth_token
                ):
                    pass
                else:
                    token = request.query.get("token", "")
                    if not self._constant_compare(token, self.auth_token):
                        return web.json_response({"error": "Unauthorized"}, status=401)
            else:
                return web.json_response({"error": "Unauthorized"}, status=401)
        return await handler(request)

    @staticmethod
    def _constant_compare(a: str, b: str) -> bool:
        """Constant-time string comparison that handles non-ASCII safely."""
        try:
            return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
        except (UnicodeEncodeError, AttributeError):
            return False

    def setup_cors(self):
        """Setup CORS for API access."""
        # Per-origin options: wildcard gets allow_credentials=False
        # per the CORS spec; explicit origins keep allow_credentials=True.
        if "*" in self.allowed_origins:
            logger.warning("CORS origin is '*'; disabling allow_credentials per CORS spec.")

        cors_defaults = {}
        for origin in self.allowed_origins:
            if origin == "*":
                cors_defaults[origin] = aiohttp_cors.ResourceOptions(
                    allow_credentials=False,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*",
                )
            else:
                cors_defaults[origin] = aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*",
                )

        cors = aiohttp_cors.setup(
            self.app,
            defaults=cors_defaults,
        )

        # Add CORS to all routes
        for route in list(self.app.router.routes()):
            cors.add(route)

    async def start(self):
        """Start the monitoring dashboard."""
        if self.is_running:
            logger.warning("Dashboard is already running")
            return

        logger.info(f"🌐 Starting Monitoring Dashboard on http://{self.host}:{self.port}")
        self.is_running = True

        # Start update task for real-time data
        self.update_task = asyncio.create_task(self._update_loop())

        # Start web server
        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        logger.info(f"✅ Dashboard running at http://{self.host}:{self.port}")

    async def stop(self):
        """Stop the monitoring dashboard."""
        logger.info("🛑 Stopping Monitoring Dashboard")
        self.is_running = False

        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

    async def _update_loop(self):
        """Background task for sending real-time updates."""
        while self.is_running:
            try:
                # Get current metrics
                metrics = await self._get_current_metrics()

                # Send to all connected websockets
                if self.websockets:
                    message = json.dumps(
                        {
                            "type": "metrics_update",
                            "data": metrics,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                    # Send to all connected clients
                    disconnected = []
                    for ws in self.websockets:
                        try:
                            await ws.send_str(message)
                        except Exception:
                            disconnected.append(ws)

                    # Remove disconnected websockets
                    for ws in disconnected:
                        self.websockets.discard(ws)

                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(self.update_interval)

    async def dashboard_page(self, request):
        """Serve the main dashboard page."""
        html_content = self._generate_dashboard_html()
        return web.Response(text=html_content, content_type="text/html")

    async def api_status(self, request):
        """API endpoint for service status."""
        try:
            if self.evolution_service:
                status = self.evolution_service.get_service_status()
            else:
                status = {"error": "Evolution service not available"}

            return web.json_response(status)

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_metrics(self, request):
        """API endpoint for current metrics."""
        try:
            metrics = await self._get_current_metrics()
            return web.json_response(metrics)

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_report(self, request):
        """API endpoint for comprehensive report."""
        try:
            if self.evolution_service:
                report = await self.evolution_service.generate_service_report()
            else:
                report = {"error": "Evolution service not available"}

            return web.json_response(report)

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_generation_diffs(self, request):
        """API endpoint for generation diff data.

        Returns recent evolution results with unified diffs between
        original and improved code for each generation.
        """
        try:
            limit = int(request.query.get("limit", "10"))
            limit = max(1, min(limit, 50))

            if not self.evolution_service:
                return web.json_response({"error": "Evolution service not available"}, status=503)

            diffs = self.evolution_service.get_generation_diffs(limit=limit)
            return web.json_response({"generation_diffs": diffs, "count": len(diffs)})

        except ValueError as e:
            return web.json_response({"error": f"Invalid parameter: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error getting generation diffs: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def websocket_handler(self, request):
        """WebSocket handler for real-time updates."""
        # Echo the accepted subprotocol so browsers complete the handshake.
        # Per RFC 6455 §4.2.2, the server must return the selected
        # subprotocol in the response; otherwise compliant clients abort.
        accepted_protocol = None
        req_protocols = request.headers.get("Sec-WebSocket-Protocol", "")
        for proto in req_protocols.split(","):
            proto = proto.strip()
            if proto.startswith("bearer."):
                accepted_protocol = proto
                break

        ws = web.WebSocketResponse(
            protocols=(accepted_protocol,) if accepted_protocol else (),
        )
        await ws.prepare(request)

        # Add to active connections
        self.websockets.add(ws)
        logger.info("New WebSocket connection established")

        try:
            # Send initial data
            initial_metrics = await self._get_current_metrics()
            await ws.send_str(
                json.dumps(
                    {
                        "type": "initial_data",
                        "data": initial_metrics,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

            # Handle incoming messages
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        # Handle client requests here if needed
                        logger.debug(f"Received WebSocket message: {data}")
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in WebSocket message: {msg.data}")
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.websockets.discard(ws)
            logger.info("WebSocket connection closed")

        return ws

    async def _get_current_metrics(self) -> dict[str, Any]:
        """Get current system metrics."""
        try:
            if not self.evolution_service:
                return {"error": "Evolution service not available"}

            # Get service status
            status = self.evolution_service.get_service_status()

            # Get bidirectional evolution status
            evolution_status = self.evolution_service.bidirectional_manager.get_evolution_status()

            # Get training manager status
            training_status = await self.evolution_service.bidirectional_manager.training_manager.get_training_status()

            # Combine metrics
            metrics = {
                "service_status": status,
                "evolution_status": evolution_status,
                "training_status": training_status,
                "dashboard_info": {
                    "update_interval": self.update_interval,
                    "connected_clients": len(self.websockets),
                    "dashboard_uptime": status.get("uptime_seconds", 0),
                },
            }

            return metrics

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {"error": str(e)}

    def _generate_dashboard_html(self) -> str:
        """Generate the dashboard HTML page."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EVOSEAL Continuous Evolution Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
        }

        .header {
            background: rgba(0, 0, 0, 0.2);
            padding: 1rem 2rem;
            border-bottom: 2px solid rgba(255, 255, 255, 0.1);
        }

        .header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }

        .header .subtitle {
            opacity: 0.8;
            font-size: 1.1rem;
        }

        .dashboard {
            padding: 2rem;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            max-width: 1400px;
            margin: 0 auto;
        }

        .card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: transform 0.3s ease;
        }

        .card:hover {
            transform: translateY(-2px);
        }

        .card h3 {
            margin-bottom: 1rem;
            font-size: 1.3rem;
            border-bottom: 2px solid rgba(255, 255, 255, 0.3);
            padding-bottom: 0.5rem;
        }

        .metric {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.8rem;
            padding: 0.5rem;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 6px;
        }

        .metric-label {
            font-weight: 500;
        }

        .metric-value {
            font-weight: bold;
            color: #4CAF50;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-running {
            background: #4CAF50;
            box-shadow: 0 0 8px #4CAF50;
        }

        .status-stopped {
            background: #f44336;
        }

        .status-warning {
            background: #ff9800;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 0.5rem;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            transition: width 0.3s ease;
        }

        .log-container {
            grid-column: 1 / -1;
            max-height: 300px;
            overflow-y: auto;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            padding: 1rem;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
        }

        .log-entry {
            margin-bottom: 0.5rem;
            opacity: 0.9;
        }

        .timestamp {
            color: #64B5F6;
            margin-right: 1rem;
        }

        .error { color: #f44336; }
        .warning { color: #ff9800; }
        .info { color: #4CAF50; }

        .footer {
            text-align: center;
            padding: 2rem;
            opacity: 0.6;
        }

        .diff-entry {
            margin-bottom: 1rem;
            padding: 1rem;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }

        .diff-entry.failed {
            border-left-color: #f44336;
        }

        .diff-header {
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
            font-size: 0.95rem;
        }

        .diff-header .badge {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
        }

        .badge-success { background: rgba(76, 175, 80, 0.3); color: #4CAF50; }
        .badge-failed  { background: rgba(244, 67, 54, 0.3); color: #f44336; }
        .badge-fitness { background: rgba(100, 181, 246, 0.3); color: #64B5F6; }

        .diff-stats {
            display: flex;
            gap: 1rem;
            margin-bottom: 0.5rem;
            font-size: 0.85rem;
            opacity: 0.85;
        }

        .diff-content {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 6px;
            padding: 0.75rem;
            font-family: 'Courier New', monospace;
            font-size: 0.8rem;
            white-space: pre;
            overflow-x: auto;
            max-height: 300px;
            overflow-y: auto;
            display: none;
        }

        .diff-content.visible { display: block; }

        .diff-toggle {
            cursor: pointer;
            color: #64B5F6;
            font-size: 0.85rem;
            margin-top: 0.5rem;
            display: inline-block;
        }

        .diff-toggle:hover { text-decoration: underline; }

        .diff-add { color: #81C784; }
        .diff-del { color: #E57373; }
        .diff-hdr { color: #64B5F6; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧬 EVOSEAL Continuous Evolution Dashboard</h1>
        <p class="subtitle">Real-time monitoring of bidirectional evolution between EVOSEAL and its coding model</p>
    </div>

    <div class="dashboard">
        <div class="card">
            <h3>🚀 Service Status</h3>
            <div class="metric">
                <span class="metric-label">Status:</span>
                <span class="metric-value" id="service-status">
                    <span class="status-indicator status-running"></span>Loading...
                </span>
            </div>
            <div class="metric">
                <span class="metric-label">Uptime:</span>
                <span class="metric-value" id="uptime">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Last Activity:</span>
                <span class="metric-value" id="last-activity">--</span>
            </div>
        </div>

        <div class="card">
            <h3>🧬 Evolution Metrics</h3>
            <div class="metric">
                <span class="metric-label">Evolution Cycles:</span>
                <span class="metric-value" id="evolution-cycles">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">Training Cycles:</span>
                <span class="metric-value" id="training-cycles">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">Improvements:</span>
                <span class="metric-value" id="improvements">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">Success Rate:</span>
                <span class="metric-value" id="success-rate">--</span>
            </div>
        </div>

        <div class="card">
            <h3>🎯 Training Status</h3>
            <div class="metric">
                <span class="metric-label">Ready for Training:</span>
                <span class="metric-value" id="training-ready">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Training Samples:</span>
                <span class="metric-value" id="training-samples">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">Model Version:</span>
                <span class="metric-value" id="model-version">--</span>
            </div>
        </div>

        <div class="card">
            <h3>📊 Performance</h3>
            <div class="metric">
                <span class="metric-label">Cycles/Hour:</span>
                <span class="metric-value" id="cycles-per-hour">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Connected Clients:</span>
                <span class="metric-value" id="connected-clients">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">Data Directory:</span>
                <span class="metric-value" id="data-dir">--</span>
            </div>
        </div>

        <div class="card log-container">
            <h3>📝 Recent Activity</h3>
            <div id="activity-log">
                <div class="log-entry info">
                    <span class="timestamp">[Loading...]</span>
                    Connecting to evolution service...
                </div>
            </div>
        </div>

        <div class="card" style="grid-column: 1 / -1;">
            <h3>🔄 Generation Diffs</h3>
            <div id="generation-diffs">
                <p style="opacity: 0.7;">Loading generation diffs...</p>
            </div>
        </div>
    </div>

    <div class="footer">
        <p>EVOSEAL Bidirectional Evolution System | Phase 3: Continuous Improvement Loop</p>
    </div>

    <script>
        // WebSocket connection for real-time updates
        let ws = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;

        let authToken = null;

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;

            // Read token from page URL query param (set by the operator).
            // The token is sent via Sec-WebSocket-Protocol header so it does
            // not appear in server/proxy access logs.
            if (!authToken) {
                const params = new URLSearchParams(window.location.search);
                authToken = params.get('token');
            }

            try {
                ws = new WebSocket(wsUrl, authToken ? ['bearer.' + authToken] : undefined);
            } catch (e) {
                console.error('WebSocket constructor failed (bad subprotocol?):', e);
                addLogEntry('WebSocket setup error: ' + e.message, 'error');
                return;
            }

            ws.onopen = function() {
                console.log('WebSocket connected');
                reconnectAttempts = 0;
                addLogEntry('Connected to evolution service', 'info');
            };

            ws.onmessage = function(event) {
                try {
                    const message = JSON.parse(event.data);
                    updateDashboard(message.data);
                } catch (e) {
                    console.error('Error parsing WebSocket message:', e);
                }
            };

            ws.onclose = function() {
                console.log('WebSocket disconnected');
                addLogEntry('Disconnected from evolution service', 'warning');

                // Attempt to reconnect
                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    setTimeout(connectWebSocket, 5000);
                }
            };

            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                addLogEntry('Connection error', 'error');
            };
        }

        function updateDashboard(data) {
            try {
                // Service status
                if (data.service_status) {
                    const status = data.service_status;
                    document.getElementById('service-status').innerHTML =
                        `<span class="status-indicator ${status.is_running ? 'status-running' : 'status-stopped'}"></span>
                         ${status.is_running ? 'Running' : 'Stopped'}`;

                    if (status.uptime_seconds) {
                        document.getElementById('uptime').textContent = formatDuration(status.uptime_seconds);
                    }

                    if (status.statistics && status.statistics.last_activity) {
                        document.getElementById('last-activity').textContent =
                            formatTimestamp(status.statistics.last_activity);
                    }

                    // Evolution metrics
                    if (status.statistics) {
                        const stats = status.statistics;
                        document.getElementById('evolution-cycles').textContent =
                            stats.evolution_cycles_completed || 0;
                        document.getElementById('training-cycles').textContent =
                            stats.training_cycles_triggered || 0;
                        document.getElementById('improvements').textContent =
                            stats.successful_improvements || 0;

                        // Calculate success rate
                        if (stats.training_cycles_triggered > 0) {
                            const rate = (stats.successful_improvements / stats.training_cycles_triggered * 100).toFixed(1);
                            document.getElementById('success-rate').textContent = `${rate}%`;
                        }
                    }
                }

                // Training status
                if (data.training_status) {
                    const training = data.training_status;
                    document.getElementById('training-ready').textContent =
                        training.ready_for_training ? 'Yes' : 'No';
                    document.getElementById('training-samples').textContent =
                        training.training_candidates || 0;
                }

                // Dashboard info
                if (data.dashboard_info) {
                    document.getElementById('connected-clients').textContent =
                        data.dashboard_info.connected_clients || 0;
                }

            } catch (e) {
                console.error('Error updating dashboard:', e);
            }
        }

        function addLogEntry(message, type = 'info') {
            const logContainer = document.getElementById('activity-log');
            const timestamp = new Date().toLocaleTimeString();

            const entry = document.createElement('div');
            entry.className = `log-entry ${type}`;
            entry.innerHTML = `<span class="timestamp">[${timestamp}]</span>${message}`;

            logContainer.appendChild(entry);

            // Keep only last 20 entries
            while (logContainer.children.length > 20) {
                logContainer.removeChild(logContainer.firstChild);
            }

            // Scroll to bottom
            logContainer.scrollTop = logContainer.scrollHeight;
        }

        function formatDuration(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${minutes}m`;
        }

        function formatTimestamp(timestamp) {
            try {
                return new Date(timestamp).toLocaleString();
            } catch (e) {
                return timestamp;
            }
        }

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            connectWebSocket();
            loadGenerationDiffs();

            // Periodic fallback updates via HTTP
            setInterval(async function() {
                try {
                    const headers = authToken ? { 'Authorization': 'Bearer ' + authToken } : {};
                    const response = await fetch('/api/metrics', { headers });
                    const data = await response.json();
                    updateDashboard(data);
                } catch (e) {
                    console.error('Error fetching metrics:', e);
                }
            }, 30000); // Every 30 seconds

            // Refresh generation diffs every 5 minutes
            setInterval(loadGenerationDiffs, 300000);
        });

        async function loadGenerationDiffs() {
            try {
                const headers = authToken ? { 'Authorization': 'Bearer ' + authToken } : {};
                const resp = await fetch('/api/generation-diffs?limit=10', { headers });
                if (!resp.ok) return;
                const data = await resp.json();
                renderGenerationDiffs(data.generation_diffs || []);
            } catch (e) {
                console.error('Error loading generation diffs:', e);
            }
        }

        function renderGenerationDiffs(diffs) {
            const container = document.getElementById('generation-diffs');
            if (!diffs.length) {
                container.innerHTML = '<p style="opacity: 0.7;">No generation data yet. Evolution results will appear here after cycles complete.</p>';
                return;
            }
            let html = '';
            diffs.forEach(function(d, idx) {
                const statusClass = d.success ? '' : ' failed';
                const statusBadge = d.success
                    ? '<span class="badge badge-success">Success</span>'
                    : '<span class="badge badge-failed">Failed</span>';
                const fitnessBadge = '<span class="badge badge-fitness">Fitness: ' +
                    (typeof d.fitness_score === 'number' ? d.fitness_score.toFixed(4) : 'N/A') + '</span>';
                const improveBadge = d.improvement_percentage > 0
                    ? '<span class="badge badge-success">+' + d.improvement_percentage.toFixed(1) + '%</span>'
                    : '';
                const diffId = 'diff-body-' + idx;

                const safeStrategy = escapeHtml(String(d.strategy));
                const safeModelVersion = escapeHtml(String(d.model_version));

                html += '<div class="diff-entry' + statusClass + '">'
                    + '<div class="diff-header">'
                    + '<span>Iteration ' + d.iteration + ' \u2022 Gen ' + d.generation + '</span>'
                    + '<span>' + statusBadge + ' ' + fitnessBadge + ' ' + improveBadge + '</span>'
                    + '</div>'
                    + '<div class="diff-stats">'
                    + '<span>Strategy: ' + safeStrategy + '</span>'
                    + '<span>Model: ' + safeModelVersion + '</span>'
                    + '<span>' + new Date(d.timestamp).toLocaleString() + '</span>'
                    + '</div>';

                if (d.unified_diff) {
                    html += '<div class="diff-toggle" onclick="toggleDiff(\'' + diffId + '\', this)">▶ Show diff</div>'
                        + '<pre class="diff-content" id="' + diffId + '">'
                        + colorizeDiff(escapeHtml(d.unified_diff)) + '</pre>';
                } else {
                    html += '<div class="diff-preview" style="opacity: 0.7; font-size: 0.85rem; margin-top: 0.5rem;">'
                        + '<em>No code changes recorded</em></div>';
                }

                html += '</div>';
            });
            container.innerHTML = html;
        }

        function toggleDiff(id, btn) {
            const el = document.getElementById(id);
            if (!el) return;
            if (el.classList.contains('visible')) {
                el.classList.remove('visible');
                btn.textContent = '▶ Show diff';
            } else {
                el.classList.add('visible');
                btn.textContent = '▼ Hide diff';
            }
        }

        function escapeHtml(str) {
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

        function colorizeDiff(html) {
            return html.split('\n').map(function(line) {
                if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@'))
                    return '<span class="diff-hdr">' + line + '</span>';
                if (line.startsWith('+'))
                    return '<span class="diff-add">' + line + '</span>';
                if (line.startsWith('-'))
                    return '<span class="diff-del">' + line + '</span>';
                return line;
            }).join('\n');
        }
    </script>
</body>
</html>
        """


async def main():
    """Main entry point for running the dashboard standalone."""
    logging.basicConfig(level=logging.INFO)

    dashboard = MonitoringDashboard()

    try:
        await dashboard.start()

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Dashboard interrupted by user")
    finally:
        await dashboard.stop()


if __name__ == "__main__":
    asyncio.run(main())
