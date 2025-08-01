# EVOSEAL Phase 3 API Reference

## Overview

EVOSEAL Phase 3 provides a comprehensive REST API and WebSocket interface through the monitoring dashboard for real-time system monitoring and control.

## Base URL

- **Development**: `http://localhost:9613`
- **Production**: `http://localhost:9613`

## REST API Endpoints

### Dashboard

#### GET /
Returns the main monitoring dashboard HTML page.

**Response**: HTML page with embedded CSS and JavaScript for real-time monitoring.

### Service Status

#### GET /api/status
Returns current service status and basic metrics.

**Response**:
```json
{
  "is_running": true,
  "start_time": "2025-01-27T00:52:56Z",
  "uptime_seconds": 3600,
  "last_evolution_check": "2025-01-27T01:52:56Z",
  "last_training_check": "2025-01-27T01:22:56Z",
  "statistics": {
    "evolution_cycles_completed": 1,
    "training_cycles_triggered": 0,
    "successful_improvements": 0,
    "total_uptime_seconds": 3600,
    "last_activity": "2025-01-27T01:52:56Z"
  }
}
```

### System Metrics

#### GET /api/metrics
Returns comprehensive system metrics including evolution, training, and performance data.

**Response**:
```json
{
  "service_status": {
    "is_running": true,
    "uptime_seconds": 3600,
    "statistics": {
      "evolution_cycles_completed": 1,
      "training_cycles_triggered": 0,
      "successful_improvements": 0
    }
  },
  "evolution_status": {
    "is_running": false,
    "last_check": "2025-01-27T01:52:56Z",
    "evolution_stats": {
      "total_evolution_cycles": 1,
      "successful_training_cycles": 0,
      "model_improvements": 0
    },
    "data_collector_stats": {
      "total_results": 0,
      "successful_results": 0,
      "failed_results": 0
    },
    "success_rate": 0.0,
    "improvement_rate": 0.0
  },
  "training_status": {
    "ready_for_training": false,
    "training_candidates": 0,
    "min_samples_required": 100,
    "current_model_version": null
  },
  "dashboard_info": {
    "update_interval": 30,
    "connected_clients": 1,
    "dashboard_uptime": 3600
  }
}
```

### Comprehensive Report

#### GET /api/report
Returns a detailed evolution report with trends, recommendations, and historical data.

**Response**:
```json
{
  "report_timestamp": "2025-01-27T01:52:56Z",
  "evolution_status": {
    "is_running": false,
    "evolution_stats": {
      "total_evolution_cycles": 1,
      "successful_training_cycles": 0,
      "model_improvements": 0,
      "start_time": "2025-01-27T00:52:56Z"
    }
  },
  "training_status": {
    "ready_for_training": false,
    "training_candidates": 0,
    "min_samples_required": 100
  },
  "runtime_statistics": {
    "total_runtime_hours": 1.0,
    "cycles_per_hour": 1.0,
    "improvements_per_day": 0.0
  },
  "evolution_trends": {
    "insufficient_data": true
  },
  "recent_history": [],
  "recommendations": [
    "No evolution cycles completed yet. Ensure EVOSEAL is generating evolution data.",
    "Evolution system appears to be functioning normally."
  ]
}
```

## WebSocket API

### Connection

#### WS /ws
Establishes a WebSocket connection for real-time updates.

**URL**: `ws://localhost:9613/ws`

### Message Types

#### Initial Data
Sent immediately upon connection establishment.

```json
{
  "type": "initial_data",
  "data": {
    "service_status": { /* same as /api/metrics */ },
    "evolution_status": { /* evolution data */ },
    "training_status": { /* training data */ }
  },
  "timestamp": "2025-01-27T01:52:56Z"
}
```

#### Metrics Update
Sent every 30 seconds (configurable) with current system metrics.

```json
{
  "type": "metrics_update",
  "data": {
    "service_status": { /* updated service status */ },
    "evolution_status": { /* updated evolution status */ },
    "training_status": { /* updated training status */ },
    "dashboard_info": { /* dashboard information */ }
  },
  "timestamp": "2025-01-27T01:53:26Z"
}
```

## Data Models

### Service Status
```typescript
interface ServiceStatus {
  is_running: boolean;
  start_time: string | null;
  uptime_seconds: number;
  last_evolution_check: string | null;
  last_training_check: string | null;
  statistics: {
    evolution_cycles_completed: number;
    training_cycles_triggered: number;
    successful_improvements: number;
    total_uptime_seconds: number;
    last_activity: string | null;
  };
}
```

### Evolution Status
```typescript
interface EvolutionStatus {
  is_running: boolean;
  last_check: string | null;
  evolution_stats: {
    total_evolution_cycles: number;
    successful_training_cycles: number;
    model_improvements: number;
    start_time: string | null;
    last_improvement: string | null;
  };
  data_collector_stats: {
    total_results: number;
    successful_results: number;
    failed_results: number;
    average_quality_score: number;
  };
  recent_cycles: number;
  output_directory: string;
  success_rate?: number;
  improvement_rate?: number;
}
```

### Training Status
```typescript
interface TrainingStatus {
  ready_for_training: boolean;
  training_candidates: number;
  min_samples_required: number;
  current_model_version: string | null;
  last_training_time: string | null;
  training_in_progress: boolean;
}
```

### Evolution Report
```typescript
interface EvolutionReport {
  report_timestamp: string;
  evolution_status: EvolutionStatus;
  training_status: TrainingStatus;
  runtime_statistics: {
    total_runtime_hours: number;
    cycles_per_hour: number;
    improvements_per_day: number;
  };
  evolution_trends: {
    insufficient_data?: boolean;
    total_cycles_analyzed?: number;
    average_score?: number;
    best_score?: number;
    worst_score?: number;
    latest_score?: number;
    score_improvement?: number;
    trending_upward?: boolean;
  };
  recent_history: EvolutionCycle[];
  recommendations: string[];
}
```

### Evolution Cycle
```typescript
interface EvolutionCycle {
  cycle_start: string;
  cycle_end: string;
  results: {
    success: boolean;
    validation_results?: {
      overall_score: number;
      passed: boolean;
    };
    error?: string;
  };
}
```

## Error Handling

### HTTP Error Responses

All API endpoints return appropriate HTTP status codes:

- `200 OK`: Successful request
- `404 Not Found`: Endpoint not found
- `500 Internal Server Error`: Server error

Error responses include a JSON object with error details:

```json
{
  "error": "Error description",
  "timestamp": "2025-01-27T01:52:56Z"
}
```

### WebSocket Error Handling

WebSocket connections handle errors gracefully:

- **Connection Lost**: Automatic reconnection attempts (up to 5 times)
- **Invalid Messages**: Logged and ignored
- **Server Errors**: Connection closed with error event

## Rate Limiting

### API Endpoints
- No rate limiting currently implemented
- Recommended: Max 60 requests per minute per client

### WebSocket
- Updates sent every 30 seconds
- No client-initiated message rate limiting

## Authentication

### Current Implementation
- No authentication required (local access only)
- Dashboard only accessible on localhost interface

### Security Considerations
- Dashboard binds only to localhost (127.0.0.1)
- No external network access
- Runs as user service (no root privileges)

## CORS Configuration

Cross-Origin Resource Sharing (CORS) is configured to allow:
- **Origins**: All origins (`*`)
- **Methods**: All methods
- **Headers**: All headers
- **Credentials**: Allowed

## Usage Examples

### JavaScript/Browser

#### Fetch Service Status
```javascript
async function getServiceStatus() {
  try {
    const response = await fetch('/api/status');
    const status = await response.json();
    console.log('Service Status:', status);
    return status;
  } catch (error) {
    console.error('Error fetching status:', error);
  }
}
```

#### WebSocket Connection
```javascript
const ws = new WebSocket('ws://localhost:9613/ws');

ws.onopen = function() {
  console.log('WebSocket connected');
};

ws.onmessage = function(event) {
  const message = JSON.parse(event.data);
  console.log('Received:', message.type, message.data);

  if (message.type === 'metrics_update') {
    updateDashboard(message.data);
  }
};

ws.onclose = function() {
  console.log('WebSocket disconnected');
  // Implement reconnection logic
};
```

### Python

#### Fetch Metrics
```python
import aiohttp
import asyncio

async def get_metrics():
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:9613/api/metrics') as response:
            if response.status == 200:
                metrics = await response.json()
                return metrics
            else:
                print(f"Error: {response.status}")
                return None

# Usage
metrics = asyncio.run(get_metrics())
print(metrics)
```

#### WebSocket Client
```python
import asyncio
import websockets
import json

async def websocket_client():
    uri = "ws://localhost:9613/ws"

    async with websockets.connect(uri) as websocket:
        async for message in websocket:
            data = json.loads(message)
            print(f"Received {data['type']}: {data['timestamp']}")

            if data['type'] == 'metrics_update':
                # Process metrics update
                process_metrics(data['data'])

# Usage
asyncio.run(websocket_client())
```

### cURL Examples

#### Get Service Status
```bash
curl -X GET http://localhost:9613/api/status | jq .
```

#### Get Comprehensive Report
```bash
curl -X GET http://localhost:9613/api/report | jq .recommendations
```

#### Health Check
```bash
# Check if service is responding
curl -f http://localhost:9613/api/status > /dev/null && echo "Service OK" || echo "Service Down"
```

## Monitoring Integration

### Prometheus Metrics (Future)

Planned Prometheus metrics endpoint:

```
# HELP evoseal_evolution_cycles_total Total number of evolution cycles
# TYPE evoseal_evolution_cycles_total counter
evoseal_evolution_cycles_total 1

# HELP evoseal_training_cycles_total Total number of training cycles
# TYPE evoseal_training_cycles_total counter
evoseal_training_cycles_total 0

# HELP evoseal_model_improvements_total Total number of successful model improvements
# TYPE evoseal_model_improvements_total counter
evoseal_model_improvements_total 0

# HELP evoseal_service_uptime_seconds Service uptime in seconds
# TYPE evoseal_service_uptime_seconds gauge
evoseal_service_uptime_seconds 3600
```

### Health Check Endpoint (Future)

Planned health check endpoint:

```
GET /health

Response:
{
  "status": "healthy",
  "checks": {
    "service": "ok",
    "ollama": "ok",
    "devstral": "ok",
    "database": "ok"
  },
  "timestamp": "2025-01-27T01:52:56Z"
}
```

## Changelog

### Version 0.3.0 (Phase 3 Release)
- Added complete REST API for monitoring
- Implemented WebSocket real-time updates
- Added comprehensive metrics and reporting
- Integrated with systemd service
- Added CORS support for web integration

### Future Enhancements
- Authentication and authorization
- Rate limiting
- Prometheus metrics endpoint
- Health check endpoint
- API versioning
- OpenAPI/Swagger documentation

## Support

For API support and questions:
- Check the [Phase 3 Documentation](PHASE3_BIDIRECTIONAL_EVOLUTION.md)
- Review the [Deployment Guide](DEPLOYMENT_GUIDE.md)
- Examine the dashboard source code in `evoseal/services/monitoring_dashboard.py`
