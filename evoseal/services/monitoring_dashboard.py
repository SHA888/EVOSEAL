"""
Web-based monitoring dashboard for EVOSEAL continuous evolution.

This module provides a real-time dashboard for monitoring the bidirectional
evolution system, displaying metrics, progress, and system health.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import aiohttp
from aiohttp import web, WSMsgType
import aiohttp_cors
import weakref

from .continuous_evolution_service import ContinuousEvolutionService


logger = logging.getLogger(__name__)


class MonitoringDashboard:
    """
    Web-based monitoring dashboard for continuous evolution.
    
    Provides real-time monitoring of evolution progress, training cycles,
    model improvements, and system health through a web interface.
    """
    
    def __init__(
        self,
        evolution_service: Optional[ContinuousEvolutionService] = None,
        host: str = "localhost",
        port: int = 8081,
        update_interval: int = 30
    ):
        """
        Initialize the monitoring dashboard.
        
        Args:
            evolution_service: The continuous evolution service to monitor
            host: Dashboard host address
            port: Dashboard port
            update_interval: Seconds between dashboard updates
        """
        self.evolution_service = evolution_service
        self.host = host
        self.port = port
        self.update_interval = update_interval
        
        # Web application
        self.app = web.Application()
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
        self.app.router.add_get('/', self.dashboard_page)
        self.app.router.add_get('/api/status', self.api_status)
        self.app.router.add_get('/api/metrics', self.api_metrics)
        self.app.router.add_get('/api/report', self.api_report)
        self.app.router.add_get('/ws', self.websocket_handler)
        # Static files embedded in HTML, no separate static directory needed
    
    def setup_cors(self):
        """Setup CORS for API access."""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
        
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
                    message = json.dumps({
                        "type": "metrics_update",
                        "data": metrics,
                        "timestamp": datetime.now().isoformat()
                    })
                    
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
        return web.Response(text=html_content, content_type='text/html')
    
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
    
    async def websocket_handler(self, request):
        """WebSocket handler for real-time updates."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Add to active connections
        self.websockets.add(ws)
        logger.info("New WebSocket connection established")
        
        try:
            # Send initial data
            initial_metrics = await self._get_current_metrics()
            await ws.send_str(json.dumps({
                "type": "initial_data",
                "data": initial_metrics,
                "timestamp": datetime.now().isoformat()
            }))
            
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
    
    async def _get_current_metrics(self) -> Dict[str, Any]:
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
                    "dashboard_uptime": status.get("uptime_seconds", 0)
                }
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
    </style>
</head>
<body>
    <div class="header">
        <h1>🧬 EVOSEAL Continuous Evolution Dashboard</h1>
        <p class="subtitle">Real-time monitoring of bidirectional evolution between EVOSEAL and Devstral</p>
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
    </div>
    
    <div class="footer">
        <p>EVOSEAL Bidirectional Evolution System | Phase 3: Continuous Improvement Loop</p>
    </div>
    
    <script>
        // WebSocket connection for real-time updates
        let ws = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
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
            
            // Periodic fallback updates via HTTP
            setInterval(async function() {
                try {
                    const response = await fetch('/api/metrics');
                    const data = await response.json();
                    updateDashboard(data);
                } catch (e) {
                    console.error('Error fetching metrics:', e);
                }
            }, 30000); // Every 30 seconds
        });
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
