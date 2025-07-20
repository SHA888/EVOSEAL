# Event System

The EVOSEAL workflow engine includes a powerful event system that allows you to react to various stages of workflow execution. This document explains how to use the event system effectively.

## Table of Contents
- [Overview](#overview)
- [Event Types](#event-types)
- [Event Object](#event-object)
- [Subscribing to Events](#subscribing-to-events)
- [Event Handling](#event-handling)
- [Error Handling](#error-handling)
- [Advanced Usage](#advanced-usage)
- [Best Practices](#best-practices)

## Overview

The event system is built around the `EventBus` class, which provides a publish-subscribe mechanism for workflow events. The `WorkflowEngine` integrates with this system to emit events at key points during workflow execution.

## Event Types

The system defines several standard event types:

```python
class EventType(Enum):
    # Workflow events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"

    # Step events
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"

    # Custom events
    CUSTOM = "custom"
```

## Event Object

Events are represented by the `Event` class, which contains:

- `event_type`: The type of event (from EventType or custom string)
- `source`: Identifier for the event source
- `data`: Dictionary containing event-specific data
- `timestamp`: When the event was created
- `context`: Additional context data
- `stop_propagation()`: Method to stop further event processing

## Subscribing to Events

### Using the WorkflowEngine

```python
engine = WorkflowEngine()

# Using decorator syntax
@engine.register_event_handler(EventType.WORKFLOW_STARTED)
def on_workflow_start(event):
    print(f"Workflow started: {event.data['workflow']}")

# Using method call
def on_step_complete(event):
    print(f"Step completed: {event.data['step']}")

engine.register_event_handler(EventType.STEP_COMPLETED, on_step_complete)
```

### Using the EventBus Directly

```python
from evoseal.core.events import event_bus

def custom_handler(event):
    print(f"Custom event: {event.data}")

event_bus.subscribe("custom_event", custom_handler)
```

## Event Handling

### Synchronous Handlers

Synchronous handlers are simple functions that take an event parameter:

```python
def handle_event(event):
    print(f"Processing event: {event.event_type}")
    print(f"Event data: {event.data}")
```

### Asynchronous Handlers

For I/O-bound operations, use async handlers:

```python
async def async_handler(event):
    # Perform async operations
    await asyncio.sleep(1)
    print(f"Async handling: {event.event_type}")
```

## Error Handling

Errors in event handlers are caught and logged but don't affect workflow execution:

```python
def error_prone_handler(event):
    try:
        # Potentially failing code
        result = 1 / 0
    except Exception as e:
        # Log the error but don't crash
        logger.error(f"Error in handler: {e}")
```

## Advanced Usage

### Event Filtering

Filter which events are handled:

```python
def only_important(event):
    return event.data.get('priority', 0) > 5

@engine.register_event_handler("data_ready", filter_fn=only_important)
def handle_important_data(event):
    print("Important data received!")
```

### Handler Priority

Control the order of handler execution:

```python
@engine.register_event_handler("process_data", priority=10)
def high_priority_handler(event):
    print("This runs first")

@engine.register_event_handler("process_data", priority=1)
def low_priority_handler(event):
    print("This runs later")
```

### Custom Events

Emit and handle custom events:

```python
# Publish a custom event
event = Event(
    event_type="data_processed",
    source="data_processor",
    data={"result": "success", "items_processed": 42}
)
await event_bus.publish(event)

# Subscribe to custom events
@event_bus.subscribe("data_processed")
def on_data_processed(event):
    print(f"Processed {event.data['items_processed']} items")
```

## Best Practices

1. **Keep Handlers Light**: Perform minimal processing in handlers; offload heavy work to separate tasks.
2. **Handle Exceptions**: Always include error handling in your event handlers.
3. **Use Async Wisely**: Only use async handlers when performing I/O operations.
4. **Document Events**: Document the structure of event data for each event type.
5. **Avoid Side Effects**: Keep handlers focused on a single responsibility.
6. **Test Event Handlers**: Write tests for your event handlers.

## Example: Monitoring Workflow Progress

```python
class WorkflowMonitor:
    def __init__(self, engine):
        self.engine = engine
        self.stats = {
            'started': 0,
            'completed': 0,
            'failed': 0,
            'steps': {}
        }
        self._register_handlers()

    def _register_handlers(self):
        @self.engine.register_event_handler(EventType.WORKFLOW_STARTED)
        def on_start(event):
            self.stats['started'] += 1
            print(f"Workflow started: {event.data['workflow']}")

        @self.engine.register_event_handler(EventType.WORKFLOW_COMPLETED)
        def on_complete(event):
            self.stats['completed'] += 1
            print(f"Workflow completed: {event.data['workflow']}")

        @self.engine.register_event_handler(EventType.STEP_COMPLETED)
        def on_step_complete(event):
            step_name = event.data['step']
            self.stats['steps'][step_name] = self.stats['steps'].get(step_name, 0) + 1
```

This documentation provides a comprehensive guide to using the event system in the EVOSEAL workflow engine.
