# EVOSEAL Enhanced Event System

The EVOSEAL Enhanced Event System provides comprehensive event-driven communication and monitoring capabilities for the evolution pipeline. This system supports synchronous and asynchronous event handling, specialized event types, filtering, metrics collection, and logging integration.

## Table of Contents

1. [Overview](#overview)
2. [Event Types](#event-types)
3. [Event Classes](#event-classes)
4. [Event Bus](#event-bus)
5. [Subscription and Publishing](#subscription-and-publishing)
6. [Event Filtering](#event-filtering)
7. [Metrics and Monitoring](#metrics-and-monitoring)
8. [Pipeline Integration](#pipeline-integration)
9. [Best Practices](#best-practices)
10. [Examples](#examples)

## Overview

The event system is built around several key components:

- **EventType Enum**: Comprehensive set of predefined event types
- **Event Classes**: Base and specialized event classes for different scenarios
- **EventBus**: Core event publishing and subscription mechanism
- **EnhancedEventBus**: Extended features including metrics, logging, and history
- **Utility Functions**: Helper functions for common event operations

### Key Features

- ✅ **Synchronous and Asynchronous Support**: Handle both sync and async event handlers
- ✅ **Event Filtering**: Filter events by type, source, severity, or custom criteria
- ✅ **Specialized Event Types**: ComponentEvent, ErrorEvent, ProgressEvent, MetricsEvent, StateChangeEvent
- ✅ **Event Propagation Control**: Stop event propagation when needed
- ✅ **Priority-based Handling**: Control handler execution order with priorities
- ✅ **Batch Publishing**: Publish multiple events efficiently
- ✅ **Event History**: Track and query recent event history
- ✅ **Metrics Collection**: Automatic collection of event statistics
- ✅ **Logging Integration**: Automatic logging based on event types and severity
- ✅ **Serialization Support**: Convert events to/from dictionaries for persistence

## Event Types

The system defines comprehensive event types covering all aspects of the evolution pipeline:

### Workflow Events
```python
EventType.WORKFLOW_STARTED
EventType.WORKFLOW_COMPLETED
EventType.WORKFLOW_FAILED
EventType.WORKFLOW_PAUSED
EventType.WORKFLOW_RESUMED
EventType.WORKFLOW_CANCELLED
```

### Step Events
```python
EventType.STEP_STARTED
EventType.STEP_COMPLETED
EventType.STEP_FAILED
EventType.STEP_SKIPPED
EventType.STEP_RETRYING
```

### Evolution Pipeline Events
```python
EventType.EVOLUTION_STARTED
EventType.EVOLUTION_COMPLETED
EventType.EVOLUTION_FAILED
EventType.ITERATION_STARTED
EventType.ITERATION_COMPLETED
EventType.ITERATION_FAILED
```

### Component Events
```python
EventType.COMPONENT_INITIALIZING
EventType.COMPONENT_READY
EventType.COMPONENT_STARTED
EventType.COMPONENT_STOPPED
EventType.COMPONENT_PAUSED
EventType.COMPONENT_RESUMED
EventType.COMPONENT_FAILED
EventType.COMPONENT_STATUS_CHANGED
EventType.COMPONENT_OPERATION_STARTED
EventType.COMPONENT_OPERATION_COMPLETED
EventType.COMPONENT_OPERATION_FAILED
```

### Pipeline Stage Events
```python
EventType.PIPELINE_STAGE_STARTED
EventType.PIPELINE_STAGE_COMPLETED
EventType.PIPELINE_STAGE_FAILED
```

### Error and Warning Events
```python
EventType.ERROR_OCCURRED
EventType.WARNING_ISSUED
EventType.EXCEPTION_RAISED
EventType.DEBUG_MESSAGE
EventType.INFO_MESSAGE
```

### Metrics and Monitoring Events
```python
EventType.METRICS_COLLECTED
EventType.PERFORMANCE_MEASURED
EventType.RESOURCE_USAGE_UPDATED
EventType.HEALTH_CHECK_COMPLETED
EventType.THRESHOLD_EXCEEDED
EventType.ALERT_TRIGGERED
```

### Configuration and State Events
```python
EventType.CONFIG_UPDATED
EventType.STATE_CHANGED
EventType.CHECKPOINT_CREATED
EventType.ROLLBACK_INITIATED
EventType.PROGRESS_UPDATE
```

## Event Classes

### Base Event Class

```python
@dataclass
class Event:
    event_type: EventType | str
    source: str
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    context: dict[str, Any] = field(default_factory=dict)

    def stop_propagation(self) -> None:
        """Stop further processing of this event."""

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create event from dictionary."""
```

### Specialized Event Classes

#### ComponentEvent
```python
@dataclass
class ComponentEvent(Event):
    component_type: str = field(default="")
    component_id: str = field(default="")
    operation: str = field(default="")
```

#### ErrorEvent
```python
@dataclass
class ErrorEvent(Event):
    error_type: str = field(default="")
    error_message: str = field(default="")
    stack_trace: str = field(default="")
    severity: str = field(default="error")  # warning, error, critical
    recoverable: bool = field(default=True)
```

#### ProgressEvent
```python
@dataclass
class ProgressEvent(Event):
    current: int = field(default=0)
    total: int = field(default=0)
    percentage: float = field(default=0.0)
    stage: str = field(default="")
    message: str = field(default="")
```

#### MetricsEvent
```python
@dataclass
class MetricsEvent(Event):
    metrics: dict[str, Any] = field(default_factory=dict)
    threshold_exceeded: bool = field(default=False)
    severity: str = field(default="info")
```

#### StateChangeEvent
```python
@dataclass
class StateChangeEvent(Event):
    old_state: str = field(default="")
    new_state: str = field(default="")
    entity_type: str = field(default="")
    entity_id: str = field(default="")
```

## Event Bus

### Basic EventBus

The basic EventBus provides core event publishing and subscription functionality:

```python
from evoseal.core.events import event_bus, EventType, Event

# Subscribe to events
@event_bus.subscribe(EventType.WORKFLOW_STARTED)
async def on_workflow_started(event: Event):
    print(f"Workflow started: {event.data}")

# Publish events
await event_bus.publish(
    Event(
        event_type=EventType.WORKFLOW_STARTED,
        source="my_component",
        data={"workflow_id": "wf-001"}
    )
)
```

### Enhanced EventBus

The EnhancedEventBus provides additional features:

```python
from evoseal.core.events import enhanced_event_bus

# Enable logging and metrics
enhanced_event_bus.enable_event_logging(max_history=1000)

# Get event metrics
metrics = enhanced_event_bus.get_event_metrics()

# Get event history
history = enhanced_event_bus.get_event_history(
    event_type=EventType.ERROR_OCCURRED,
    limit=50
)

# Batch publish events
events = [
    Event(EventType.STEP_STARTED, "source1", {"step": 1}),
    Event(EventType.STEP_STARTED, "source2", {"step": 2}),
]
await enhanced_event_bus.publish_batch(events)
```

## Subscription and Publishing

### Subscription Patterns

#### 1. Decorator Subscription
```python
from evoseal.core.events import subscribe, EventType

@subscribe(EventType.ERROR_OCCURRED)
async def handle_error(event: Event):
    print(f"Error: {event.data}")

@subscribe(priority=100)  # High priority
async def high_priority_handler(event: Event):
    # This runs before lower priority handlers
    pass
```

#### 2. Direct Subscription
```python
from evoseal.core.events import event_bus

async def my_handler(event: Event):
    print(f"Received: {event.event_type}")

event_bus.subscribe(EventType.WORKFLOW_STARTED, my_handler)
```

#### 3. Filtered Subscription
```python
from evoseal.core.events import subscribe, create_event_filter

# Create a filter
error_filter = create_event_filter(
    event_types=[EventType.ERROR_OCCURRED],
    sources=["component1", "component2"],
    severity_levels=["error", "critical"]
)

@subscribe(filter_fn=error_filter)
async def handle_filtered_errors(event: Event):
    print(f"Filtered error: {event.data}")
```

### Publishing Patterns

#### 1. Basic Publishing
```python
from evoseal.core.events import publish, EventType

await publish(
    EventType.WORKFLOW_STARTED,
    source="my_component",
    workflow_id="wf-001",
    timestamp="2024-01-01T10:00:00Z"
)
```

#### 2. Using Factory Functions
```python
from evoseal.core.events import create_error_event, create_progress_event

# Create and publish error event
error_event = create_error_event(
    error=ValueError("Something went wrong"),
    source="my_component",
    severity="error"
)
await event_bus.publish(error_event)

# Create and publish progress event
progress_event = create_progress_event(
    current=50,
    total=100,
    stage="processing",
    source="my_component",
    message="Half way done"
)
await event_bus.publish(progress_event)
```

#### 3. Helper Functions
```python
from evoseal.core.events import publish_component_lifecycle_event, publish_pipeline_stage_event

# Publish component lifecycle event
await publish_component_lifecycle_event(
    component_type="DGM",
    component_id="dgm-001",
    lifecycle_event="started",
    source="orchestrator"
)

# Publish pipeline stage event
await publish_pipeline_stage_event(
    stage="analyzing",
    status="completed",
    source="pipeline",
    progress={"current": 1, "total": 5}
)
```

## Event Filtering

Create sophisticated event filters to control which events are processed:

```python
from evoseal.core.events import create_event_filter, subscribe

# Filter by event types and sources
component_filter = create_event_filter(
    event_types=[EventType.COMPONENT_STARTED, EventType.COMPONENT_STOPPED],
    sources=["orchestrator", "pipeline"]
)

# Filter by severity levels
error_filter = create_event_filter(
    event_types=[EventType.ERROR_OCCURRED, EventType.WARNING_ISSUED],
    severity_levels=["error", "critical"]
)

# Custom filter function
def custom_filter(event: Event) -> bool:
    return "important" in event.data.get("tags", [])

combined_filter = create_event_filter(
    event_types=[EventType.INFO_MESSAGE],
    custom_filter=custom_filter
)

@subscribe(filter_fn=combined_filter)
async def handle_important_info(event: Event):
    print(f"Important info: {event.data}")
```

## Metrics and Monitoring

### Event Metrics

The enhanced event bus automatically collects metrics:

```python
from evoseal.core.events import enhanced_event_bus

# Get all metrics
all_metrics = enhanced_event_bus.get_event_metrics()

# Get metrics for specific event type
error_metrics = enhanced_event_bus.get_event_metrics(EventType.ERROR_OCCURRED)

# Example metrics structure:
{
    "error_occurred": {
        "count": 15,
        "first_seen": 1640995200.0,
        "last_seen": 1640995800.0,
        "sources": ["component1", "component2", "pipeline"],
        "avg_processing_time": 0.05
    }
}
```

### Event History

Track and query recent events:

```python
# Get recent events (all types)
recent_events = enhanced_event_bus.get_event_history(limit=100)

# Get recent error events
error_history = enhanced_event_bus.get_event_history(
    event_type=EventType.ERROR_OCCURRED,
    limit=50
)

# Clear history
enhanced_event_bus.clear_event_history()
```

## Pipeline Integration

The event system is deeply integrated with the evolution pipeline:

### Pipeline Events

The pipeline automatically publishes events for:

- Evolution cycle start/completion
- Iteration progress
- Pipeline stage transitions
- Component lifecycle changes
- Error conditions

### Component Integration

Components can publish events using the helper functions:

```python
from evoseal.core.events import publish_component_lifecycle_event

class MyComponent:
    async def start(self):
        await publish_component_lifecycle_event(
            component_type="MyComponent",
            component_id=self.component_id,
            lifecycle_event="started",
            source="my_component"
        )
```

## Best Practices

### 1. Event Naming and Structure

- Use descriptive event types from the EventType enum
- Include relevant context in event data
- Use consistent source naming conventions
- Add timestamps for time-sensitive events

### 2. Error Handling

- Always handle exceptions in event handlers
- Use appropriate severity levels for errors
- Include stack traces for debugging
- Mark errors as recoverable/non-recoverable

### 3. Performance Considerations

- Use event filtering to reduce handler overhead
- Batch publish events when possible
- Set appropriate priority levels
- Avoid blocking operations in handlers

### 4. Monitoring and Debugging

- Enable event logging for debugging
- Monitor event metrics for performance issues
- Use event history for troubleshooting
- Set up alerts for critical events

### 5. Testing

- Create mock event handlers for testing
- Verify event publishing in unit tests
- Test event filtering logic
- Monitor event metrics in integration tests

## Examples

### Complete Pipeline Monitoring

```python
import asyncio
from evoseal.core.events import subscribe, EventType, enhanced_event_bus

class PipelineMonitor:
    def __init__(self):
        self.setup_event_handlers()
        enhanced_event_bus.enable_event_logging()

    def setup_event_handlers(self):
        @subscribe(EventType.EVOLUTION_STARTED, priority=100)
        async def on_evolution_started(event):
            print(f"🚀 Evolution started: {event.data}")

        @subscribe(EventType.ITERATION_COMPLETED)
        async def on_iteration_completed(event):
            iteration = event.data.get('iteration', '?')
            print(f"✅ Iteration {iteration} completed")

        @subscribe(EventType.ERROR_OCCURRED, priority=200)
        async def on_error(event):
            severity = event.data.get('severity', 'unknown')
            print(f"❌ Error ({severity}): {event.data.get('error_message', 'Unknown error')}")

        @subscribe()  # Subscribe to all events
        async def log_all_events(event):
            # Custom logging logic
            pass

    async def get_status_report(self):
        metrics = enhanced_event_bus.get_event_metrics()
        history = enhanced_event_bus.get_event_history(limit=10)

        return {
            "metrics": metrics,
            "recent_events": len(history),
            "error_count": metrics.get("error_occurred", {}).get("count", 0)
        }

# Usage
monitor = PipelineMonitor()
status = await monitor.get_status_report()
```

### Custom Event Types

```python
from evoseal.core.events import Event, event_bus

# Define custom event types
CUSTOM_ANALYSIS_COMPLETED = "custom.analysis.completed"
CUSTOM_OPTIMIZATION_STARTED = "custom.optimization.started"

# Publish custom events
await event_bus.publish(
    Event(
        event_type=CUSTOM_ANALYSIS_COMPLETED,
        source="analysis_engine",
        data={
            "analysis_id": "analysis-001",
            "results": {"complexity": 8.5, "issues": 3},
            "duration": 45.2
        }
    )
)

# Subscribe to custom events
@subscribe(CUSTOM_ANALYSIS_COMPLETED)
async def handle_analysis_completed(event):
    results = event.data.get("results", {})
    print(f"Analysis completed: {results}")
```

This enhanced event system provides comprehensive monitoring and communication capabilities for the EVOSEAL evolution pipeline, enabling robust event-driven architecture with extensive customization options.
