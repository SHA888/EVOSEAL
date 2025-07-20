# Error Handling and Resilience System

The EVOSEAL pipeline includes a comprehensive error handling and resilience system designed to ensure robust operation in production environments. This system provides automatic error recovery, circuit breakers, health monitoring, structured logging, and graceful degradation capabilities.

## Table of Contents

1. [Overview](#overview)
2. [Core Components](#core-components)
3. [Error Handling Framework](#error-handling-framework)
4. [Resilience Mechanisms](#resilience-mechanisms)
5. [Error Recovery System](#error-recovery-system)
6. [Enhanced Logging](#enhanced-logging)
7. [Integration Guide](#integration-guide)
8. [Configuration](#configuration)
9. [Monitoring and Alerting](#monitoring-and-alerting)
10. [Best Practices](#best-practices)
11. [Troubleshooting](#troubleshooting)
12. [API Reference](#api-reference)

## Overview

The error handling and resilience system provides:

- **Comprehensive Error Classification**: Structured error types with context and severity
- **Automatic Recovery**: Multi-level recovery strategies with exponential backoff
- **Circuit Breakers**: Failure isolation to prevent cascade failures
- **Health Monitoring**: Real-time component health tracking and alerting
- **Structured Logging**: Enhanced logging with metrics and analysis
- **Graceful Degradation**: Fallback mechanisms for continued operation
- **Resilience Orchestration**: Centralized management of all resilience mechanisms

## Core Components

### 1. Error Framework (`evoseal.core.errors`)

Provides structured error handling with:

```python
from evoseal.core.errors import BaseError, ErrorCategory, ErrorSeverity

# Custom error with context
error = BaseError(
    "Database connection failed",
    code="DB_CONNECTION_ERROR",
    category=ErrorCategory.INTEGRATION,
    severity=ErrorSeverity.ERROR
).with_context(
    component="database",
    operation="connect",
    retry_count=3
)
```

### 2. Resilience Manager (`evoseal.core.resilience`)

Manages circuit breakers, health monitoring, and failure isolation:

```python
from evoseal.core.resilience import resilience_manager, CircuitBreakerConfig

# Register circuit breaker
resilience_manager.register_circuit_breaker(
    "api_service",
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60,
        success_threshold=3
    )
)

# Execute with resilience
result = await resilience_manager.execute_with_resilience(
    "api_service", "fetch_data", api_call, param1, param2
)
```

### 3. Error Recovery System (`evoseal.core.error_recovery`)

Provides intelligent error recovery with multiple strategies:

```python
from evoseal.core.error_recovery import with_error_recovery, RecoveryStrategy

@with_error_recovery("component", "operation")
async def risky_operation():
    # Your code here
    pass

# Custom recovery strategy
strategy = RecoveryStrategy(
    max_retries=5,
    retry_delay=2.0,
    backoff_multiplier=1.5,
    recovery_actions=[RecoveryAction.RETRY, RecoveryAction.FALLBACK]
)
```

### 4. Enhanced Logging (`evoseal.core.logging_system`)

Structured logging with monitoring and analysis:

```python
from evoseal.core.logging_system import get_logger

logger = get_logger("my_component")

# Structured logging
logger.log_component_operation(
    component="api_client",
    operation="fetch_data",
    status="success",
    duration=1.5,
    records_processed=100
)

# Error logging with context
logger.log_error_with_context(
    error=exception,
    component="api_client",
    operation="fetch_data",
    request_id="req_123",
    user_id="user_456"
)
```

### 5. Resilience Integration (`evoseal.core.resilience_integration`)

Orchestrates all resilience mechanisms:

```python
from evoseal.core.resilience_integration import initialize_resilience_system

# Initialize complete resilience system
await initialize_resilience_system()

# Get comprehensive status
status = get_resilience_status()
```

## Error Handling Framework

### Error Classification

Errors are classified by category and severity:

**Categories:**
- `VALIDATION`: Input validation errors
- `CONFIGURATION`: Configuration issues
- `RUNTIME`: Runtime execution errors
- `INTEGRATION`: External system integration errors
- `NETWORK`: Network connectivity issues
- `PERMISSION`: Authorization/permission errors
- `RESOURCE`: Resource exhaustion (memory, disk, etc.)
- `TIMEOUT`: Operation timeout errors

**Severity Levels:**
- `DEBUG`: Debug information
- `INFO`: Informational messages
- `WARNING`: Warning conditions
- `ERROR`: Error conditions
- `CRITICAL`: Critical system errors

### Error Context

All errors include rich context information:

```python
error = BaseError("Operation failed").with_context(
    component="data_processor",
    operation="transform_data",
    input_size=1000,
    memory_usage="512MB",
    execution_time=30.5
)
```

### Error Decorators

Use decorators for automatic error handling:

```python
from evoseal.core.errors import handle_errors, retry_on_error, error_boundary

@handle_errors(reraise=True, log_level=logging.ERROR)
@retry_on_error(max_retries=3, delay=1.0)
async def network_operation():
    # Network call that may fail
    pass

@error_boundary(default="fallback_value")
def safe_operation():
    # Operation that returns fallback on error
    pass
```

## Resilience Mechanisms

### Circuit Breakers

Circuit breakers prevent cascade failures by isolating failing components:

```python
# Configure circuit breaker
config = CircuitBreakerConfig(
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout=60,      # Wait 60s before testing
    success_threshold=3,      # Close after 3 successes
    timeout=30.0             # Operation timeout
)

resilience_manager.register_circuit_breaker("service_name", config)
```

**Circuit States:**
- `CLOSED`: Normal operation, requests pass through
- `OPEN`: Failing state, requests are blocked
- `HALF_OPEN`: Testing state, limited requests allowed

### Health Monitoring

Continuous monitoring of component health:

```python
# Health metrics are automatically collected
health = resilience_manager.health_monitor.get_component_health("component")

print(f"Health: {health.health_status}")
print(f"Success Rate: {health.success_rate:.2%}")
print(f"Consecutive Failures: {health.consecutive_failures}")
```

**Health States:**
- `HEALTHY`: Normal operation (>90% success rate)
- `DEGRADED`: Reduced performance (50-90% success rate)
- `UNHEALTHY`: Poor performance (<50% success rate)
- `CRITICAL`: Severe issues (>10 consecutive failures)

### Failure Isolation

Isolate failing components to prevent system-wide failures:

```python
# Set isolation policy
resilience_manager.set_isolation_policy("database", {"cache", "analytics"})

# When database fails, cache and analytics are isolated
```

## Error Recovery System

### Recovery Strategies

Multiple recovery strategies are available:

1. **Retry with Backoff**: Exponential backoff retry
2. **Fallback**: Use alternative implementation
3. **Circuit Breaking**: Isolate failing component
4. **Component Restart**: Restart failed component
5. **Graceful Degradation**: Reduced functionality mode
6. **Escalation**: Forward to higher-level handler

### Recovery Configuration

```python
from evoseal.core.error_recovery import RecoveryStrategy, RecoveryAction

strategy = RecoveryStrategy(
    max_retries=3,
    retry_delay=1.0,
    backoff_multiplier=2.0,
    max_delay=60.0,
    timeout=30.0,
    recovery_actions=[
        RecoveryAction.RETRY,
        RecoveryAction.FALLBACK,
        RecoveryAction.ESCALATE
    ]
)
```

### Fallback Mechanisms

Register fallback handlers for graceful degradation:

```python
async def api_fallback(*args, context=None, **kwargs):
    # Return cached data or default response
    return {"status": "fallback", "data": cached_data}

error_recovery_manager.fallback_manager.register_fallback(
    "api_service", "fetch_data", api_fallback
)
```

### Custom Recovery Actions

Implement custom recovery logic:

```python
async def custom_recovery(component: str, operation: str, error: Exception):
    # Custom recovery logic
    logger.info(f"Executing custom recovery for {component}")
    await restart_component(component)
    await clear_cache(component)

error_recovery_manager.register_recovery_strategy("component", custom_recovery)
```

## Enhanced Logging

### Structured Logging

All logging uses structured format with rich context:

```python
logger = get_logger("component_name")

# Pipeline stage logging
logger.log_pipeline_stage(
    stage="data_processing",
    status="started",
    iteration=5,
    input_size=1000
)

# Component operation logging
logger.log_component_operation(
    component="data_processor",
    operation="transform",
    status="success",
    duration=2.5,
    records_processed=1000,
    memory_used="256MB"
)

# Performance metric logging
logger.log_performance_metric(
    metric_name="throughput",
    value=500,
    unit="records/sec",
    component="processor"
)
```

### Log Analysis and Monitoring

Automatic log analysis with alerting:

```python
# Get logging metrics
metrics = logger.get_metrics()
print(f"Total logs: {metrics.total_logs}")
print(f"Error rate: {metrics.error_rate:.2%}")
print(f"Logs per minute: {metrics.avg_logs_per_minute}")

# Recent logs with filtering
recent_errors = logger.get_recent_logs(
    count=50,
    level=LogLevel.ERROR,
    component="api_client"
)
```

### Log Aggregation

Centralized log management:

```python
from evoseal.core.logging_system import logging_manager

# Get global metrics across all loggers
global_metrics = logging_manager.get_global_metrics()

# Component-specific logger
component_logger = logging_manager.get_logger("my_component")
```

## Integration Guide

### Pipeline Integration

The resilience system is automatically integrated into the evolution pipeline:

```python
from evoseal.core.evolution_pipeline import EvolutionPipeline

# Pipeline automatically uses resilience mechanisms
pipeline = EvolutionPipeline(config)

# Initialize with resilience
await pipeline.initialize_components()

# Run with automatic error handling and recovery
results = await pipeline.run_evolution_cycle(iterations=5)
```

### Manual Integration

For custom components, integrate resilience manually:

```python
from evoseal.core.resilience import resilience_manager
from evoseal.core.error_recovery import with_error_recovery

class MyComponent:
    @with_error_recovery("my_component", "process_data")
    async def process_data(self, data):
        return await resilience_manager.execute_with_resilience(
            "my_component", "process", self._internal_process, data
        )

    async def _internal_process(self, data):
        # Your processing logic
        return processed_data
```

### Event Integration

Resilience events are published to the event system:

```python
from evoseal.core.events import event_bus

# Subscribe to resilience events
async def handle_resilience_event(event):
    if event.event_type == "ERROR_RECOVERY_SUCCESS":
        print(f"Recovery successful: {event.data}")
    elif event.event_type == "CIRCUIT_BREAKER_OPEN":
        print(f"Circuit breaker opened: {event.data}")

event_bus.subscribe("ERROR_RECOVERY_SUCCESS", handle_resilience_event)
event_bus.subscribe("CIRCUIT_BREAKER_OPEN", handle_resilience_event)
```

## Configuration

### Environment Variables

Configure resilience system via environment variables:

```bash
# Circuit breaker settings
EVOSEAL_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
EVOSEAL_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Recovery settings
EVOSEAL_RECOVERY_MAX_RETRIES=3
EVOSEAL_RECOVERY_RETRY_DELAY=1.0

# Health monitoring
EVOSEAL_HEALTH_CHECK_INTERVAL=30
EVOSEAL_HEALTH_WINDOW_SIZE=100

# Logging settings
EVOSEAL_LOG_LEVEL=INFO
EVOSEAL_LOG_AGGREGATION_ENABLED=true
```

### Configuration Files

Use YAML or JSON configuration:

```yaml
# resilience_config.yaml
resilience:
  circuit_breakers:
    api_service:
      failure_threshold: 5
      recovery_timeout: 60
      success_threshold: 3

  recovery:
    max_retries: 3
    retry_delay: 1.0
    backoff_multiplier: 2.0

  health_monitoring:
    check_interval: 30
    window_size: 100

  logging:
    level: INFO
    enable_monitoring: true
    log_directory: "./logs"
```

### Programmatic Configuration

Configure via code:

```python
from evoseal.core.resilience_integration import resilience_orchestrator

# Configure resilience system
await resilience_orchestrator.initialize()

# Custom configuration
resilience_orchestrator.health_check_interval = 60
resilience_orchestrator.emergency_shutdown_enabled = True
```

## Monitoring and Alerting

### Health Checks

Automatic health monitoring with configurable intervals:

```python
# Health check results
health_status = await resilience_orchestrator._perform_health_checks()

print(f"Overall health: {health_status['overall_health']}")
for component, status in health_status['components'].items():
    print(f"{component}: {status['status']} ({status['success_rate']:.2%})")
```

### Alert Handling

Custom alert handlers for different scenarios:

```python
async def custom_alert_handler(alert):
    if alert['type'] == 'high_error_rate':
        # Send notification
        await send_notification(f"High error rate: {alert['error_rate']:.2%}")
    elif alert['type'] == 'component_unhealthy':
        # Restart component
        await restart_component(alert['component'])

resilience_orchestrator.alert_handlers.append(custom_alert_handler)
```

### Metrics Collection

Comprehensive metrics collection:

```python
# Resilience metrics
resilience_status = resilience_manager.get_resilience_status()

# Recovery statistics
recovery_stats = error_recovery_manager.get_recovery_statistics()

# Logging metrics
logging_metrics = logging_manager.get_global_metrics()

# Combined status
comprehensive_status = await resilience_orchestrator.get_comprehensive_status()
```

## Best Practices

### 1. Error Handling

- Use structured errors with appropriate categories and severity
- Include rich context in error messages
- Implement proper error boundaries
- Log errors with sufficient detail for debugging

### 2. Circuit Breakers

- Set appropriate failure thresholds based on component criticality
- Use shorter recovery timeouts for non-critical components
- Monitor circuit breaker state changes
- Implement fallback mechanisms for open circuits

### 3. Recovery Strategies

- Use exponential backoff for transient failures
- Implement fallback mechanisms for critical operations
- Set reasonable retry limits to avoid infinite loops
- Consider the cost of retries vs. fallback

### 4. Health Monitoring

- Monitor key performance indicators (success rate, response time)
- Set appropriate health check intervals
- Implement proactive alerting for degraded components
- Use health data for capacity planning

### 5. Logging

- Use structured logging with consistent field names
- Include correlation IDs for request tracing
- Set appropriate log levels for different environments
- Monitor log volume and error rates

### 6. Testing

- Test failure scenarios in development
- Verify recovery mechanisms work as expected
- Load test circuit breakers and health monitoring
- Practice incident response procedures

## Troubleshooting

### Common Issues

#### High Error Rates

```python
# Check component health
health = resilience_manager.health_monitor.get_component_health("component")
if health.error_rate > 0.1:
    print(f"High error rate detected: {health.error_rate:.2%}")

# Check recent errors
recent_errors = logger.get_recent_logs(level=LogLevel.ERROR, component="component")
for error in recent_errors:
    print(f"Error: {error.message}")
```

#### Circuit Breaker Issues

```python
# Check circuit breaker status
status = resilience_manager.get_resilience_status()
for name, cb_status in status["circuit_breakers"].items():
    if cb_status["state"] == "open":
        print(f"Circuit breaker {name} is open")
        print(f"Failure count: {cb_status['failure_count']}")
        print(f"Last failure: {cb_status['last_failure']}")
```

#### Recovery Failures

```python
# Check recovery statistics
recovery_stats = error_recovery_manager.get_recovery_statistics()
if recovery_stats["success_rate"] < 0.5:
    print(f"Low recovery success rate: {recovery_stats['success_rate']:.2%}")

# Review recent recovery attempts
for attempt in recovery_stats.get("recent_failures", []):
    print(f"Failed recovery: {attempt['component']} - {attempt['failure_mode']}")
```

### Debugging Tools

#### Enable Debug Logging

```python
# Enable debug logging
logger = get_logger("component")
logger.python_logger.setLevel(logging.DEBUG)

# Debug specific operations
logger.debug("Starting operation", operation_id="op_123", input_size=1000)
```

#### Inspect Resilience State

```python
# Get detailed status
status = await resilience_orchestrator.get_comprehensive_status()

# Pretty print status
import json
print(json.dumps(status, indent=2, default=str))
```

#### Monitor Events

```python
# Subscribe to all resilience events
async def debug_event_handler(event):
    print(f"Event: {event.event_type} - {event.data}")

event_bus.subscribe("ERROR_RECOVERY_SUCCESS", debug_event_handler)
event_bus.subscribe("CIRCUIT_BREAKER_OPEN", debug_event_handler)
event_bus.subscribe("COMPONENT_HEALTH_DEGRADED", debug_event_handler)
```

## API Reference

### Core Classes

#### `BaseError`
```python
class BaseError(Exception):
    def __init__(self, message: str, config: ErrorConfig = None, **kwargs)
    def with_context(self, **kwargs) -> BaseError
    def to_dict(self) -> Dict[str, Any]
    @classmethod
    def from_exception(cls, exc: Exception, **kwargs) -> BaseError
```

#### `ResilienceManager`
```python
class ResilienceManager:
    def register_circuit_breaker(self, name: str, config: CircuitBreakerConfig)
    def register_recovery_strategy(self, component: str, strategy: Callable)
    def register_degradation_handler(self, component: str, handler: Callable)
    async def execute_with_resilience(self, component: str, operation: str, func: Callable, *args, **kwargs) -> Any
    def get_resilience_status(self) -> Dict[str, Any]
```

#### `ErrorRecoveryManager`
```python
class ErrorRecoveryManager:
    def register_escalation_handler(self, component: str, handler: Callable)
    async def recover_from_error(self, error: Exception, component: str, operation: str, original_func: Callable, *args, **kwargs) -> Tuple[Any, RecoveryResult]
    def get_recovery_statistics(self) -> Dict[str, Any]
```

#### `StructuredLogger`
```python
class StructuredLogger:
    def log(self, level: LogLevel, message: str, category: LogCategory = LogCategory.SYSTEM, **context)
    def log_pipeline_stage(self, stage: str, status: str, iteration: int = None, **context)
    def log_component_operation(self, component: str, operation: str, status: str, duration: float = None, **context)
    def log_performance_metric(self, metric_name: str, value: Union[int, float], unit: str = "", **context)
    def log_error_with_context(self, error: Exception, component: str = None, operation: str = None, **context)
    def get_metrics(self) -> LogMetrics
    def get_recent_logs(self, count: int = 50, **filters) -> List[LogEntry]
```

### Decorators

#### `@with_error_recovery`
```python
def with_error_recovery(component: str, operation: str, recovery_strategy: RecoveryStrategy = None):
    """Decorator to add error recovery to functions."""
```

#### `@handle_errors`
```python
def handle_errors(error_types: Tuple[Type[Exception], ...] = None, reraise: bool = True, log_level: int = logging.ERROR, default_message: str = "An error occurred"):
    """Decorator for comprehensive error handling."""
```

#### `@retry_on_error`
```python
def retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: Tuple[Type[Exception], ...] = (Exception,)):
    """Decorator to retry functions on error."""
```

### Configuration Classes

#### `CircuitBreakerConfig`
```python
@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3
    timeout: float = 30.0
```

#### `RecoveryStrategy`
```python
@dataclass
class RecoveryStrategy:
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay: float = 300.0
    timeout: float = 30.0
    fallback_enabled: bool = True
    escalation_threshold: int = 5
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
```

---

This comprehensive error handling and resilience system ensures that the EVOSEAL pipeline can operate reliably in production environments, automatically recovering from failures and providing detailed monitoring and alerting capabilities.
