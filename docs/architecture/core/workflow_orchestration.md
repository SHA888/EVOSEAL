# Workflow Orchestration System

The EVOSEAL Workflow Orchestration System provides comprehensive end-to-end orchestration for evolution pipelines, including checkpointing, state persistence, recovery strategies, and execution flow optimization.

## Overview

The orchestration system is designed to manage complex, long-running evolution workflows with robust error handling, resource monitoring, and state management capabilities. It ensures reliable execution even in the face of failures, resource constraints, and system interruptions.

## Architecture

The system is built with a modular architecture consisting of four main components:

### 1. Core Orchestrator (`WorkflowOrchestrator`)
- Central coordination of workflow execution
- Integration with all other components
- Execution strategy management
- Event handling and publishing

### 2. Checkpoint Manager (`CheckpointManager`)
- Automatic and manual checkpoint creation
- State serialization and persistence
- Checkpoint metadata management
- Recovery point management

### 3. Recovery Manager (`RecoveryManager`)
- Multi-level error recovery strategies
- Retry logic with exponential backoff
- Component restart capabilities
- Custom recovery action support

### 4. Resource Monitor (`ResourceMonitor`)
- Real-time system resource monitoring
- Configurable threshold alerting
- Resource usage history tracking
- Automatic checkpoint triggers

## Key Features

### Comprehensive State Management
- **Orchestration States**: IDLE, INITIALIZING, RUNNING, PAUSED, RECOVERING, CHECKPOINTING, COMPLETED, FAILED, CANCELLED
- **Execution Context**: Complete workflow state tracking including iterations, stages, and metadata
- **Step Results**: Detailed tracking of individual workflow step execution

### Advanced Checkpointing
- **Automatic Checkpoints**: Based on iteration intervals or resource thresholds
- **Manual Checkpoints**: User-triggered checkpoints at any time
- **Recovery Checkpoints**: Created before and after recovery attempts
- **Milestone Checkpoints**: Mark significant workflow achievements
- **Error Recovery Checkpoints**: Capture state during error conditions

### Robust Recovery Strategies
- **Retry with Backoff**: Configurable retry attempts with exponential backoff
- **Checkpoint Rollback**: Restore from previous successful state
- **Component Restart**: Restart failed components
- **State Validation**: Verify and repair workflow state
- **Custom Recovery Actions**: User-defined recovery procedures

### Resource Monitoring and Management
- **CPU Monitoring**: Track CPU usage with configurable thresholds
- **Memory Monitoring**: Monitor memory consumption and availability
- **Disk Monitoring**: Track disk usage and free space
- **Network Monitoring**: Monitor network I/O (when available)
- **Alert System**: Configurable alerts for threshold violations

### Flexible Execution Strategies
- **Sequential Execution**: Steps executed in dependency order
- **Parallel Execution**: Independent steps executed concurrently
- **Adaptive Execution**: Automatically choose optimal strategy
- **Priority-Based Execution**: Execute based on step priorities

## Usage Guide

### Basic Setup

```python
from evoseal.core.orchestration import (
    WorkflowOrchestrator,
    ExecutionStrategy,
    RecoveryStrategy,
    ResourceThresholds,
)

# Create orchestrator
orchestrator = WorkflowOrchestrator(
    workspace_dir=".evoseal",
    checkpoint_interval=5,
    execution_strategy=ExecutionStrategy.ADAPTIVE,
)
```

### Workflow Configuration

```python
workflow_config = {
    "workflow_id": "evolution_workflow_001",
    "experiment_id": "exp_001",
    "iterations": 10,
    "steps": [
        {
            "name": "analyze",
            "component": "analyzer",
            "operation": "analyze_code",
            "parameters": {"depth": "full"},
            "critical": True,
            "retry_count": 3,
            "timeout": 300.0,
        },
        {
            "name": "generate",
            "component": "generator",
            "operation": "generate_improvements",
            "parameters": {"count": 5},
            "dependencies": ["analyze"],
            "critical": True,
            "retry_count": 2,
        },
        {
            "name": "evaluate",
            "component": "evaluator",
            "operation": "evaluate_changes",
            "parameters": {"metrics": ["performance", "quality"]},
            "dependencies": ["generate"],
            "critical": False,
        },
    ],
}
```

### Execution

```python
# Initialize workflow
success = await orchestrator.initialize_workflow(workflow_config)

if success:
    # Execute workflow
    result = await orchestrator.execute_workflow(pipeline_instance)

    print(f"Workflow completed: {result.success_count}/{len(result.iterations)} iterations successful")
    print(f"Total execution time: {result.total_execution_time:.2f}s")
    print(f"Checkpoints created: {result.checkpoints_created}")
```

### Advanced Configuration

#### Recovery Strategy

```python
recovery_strategy = RecoveryStrategy(
    max_retries=3,
    retry_delay=5.0,
    exponential_backoff=True,
    backoff_multiplier=2.0,
    max_retry_delay=300.0,
    checkpoint_rollback=True,
    component_restart=True,
    state_validation=True,
    recovery_timeout=600.0,
)

orchestrator = WorkflowOrchestrator(
    recovery_strategy=recovery_strategy,
    # ... other parameters
)
```

#### Resource Monitoring

```python
resource_thresholds = ResourceThresholds(
    memory_warning=0.7,      # 70% memory usage warning
    memory_critical=0.85,    # 85% memory usage critical
    cpu_warning=0.8,         # 80% CPU usage warning
    cpu_critical=0.9,        # 90% CPU usage critical
    disk_warning=0.8,        # 80% disk usage warning
    disk_critical=0.9,       # 90% disk usage critical
)

orchestrator = WorkflowOrchestrator(
    resource_thresholds=resource_thresholds,
    monitoring_interval=30.0,  # Check every 30 seconds
    # ... other parameters
)
```

### Workflow Control

```python
# Pause workflow
await orchestrator.pause_workflow()

# Resume workflow
await orchestrator.resume_workflow()

# Cancel workflow
await orchestrator.cancel_workflow()

# Get status
status = orchestrator.get_workflow_status()
print(f"Current state: {status['state']}")
print(f"Current iteration: {status['execution_context']['current_iteration']}")
```

### Checkpoint Management

```python
# Create manual checkpoint
checkpoint_id = await orchestrator._create_checkpoint(CheckpointType.MANUAL)

# Resume from checkpoint
result = await orchestrator.execute_workflow(
    pipeline_instance,
    resume_from_checkpoint=checkpoint_id
)

# List checkpoints
checkpoints = orchestrator.checkpoint_manager.list_checkpoints(limit=10)
for cp in checkpoints:
    print(f"{cp.checkpoint_id}: {cp.checkpoint_type.value} at {cp.timestamp}")

# Cleanup old checkpoints
deleted_count = orchestrator.checkpoint_manager.cleanup_old_checkpoints(
    max_age_days=7,
    max_count=50,
    keep_milestone=True
)
```

## Workflow Step Configuration

### Step Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `step_id` | str | Unique identifier for the step | Auto-generated |
| `name` | str | Human-readable step name | Required |
| `component` | str | Component name to execute | Required |
| `operation` | str | Method/operation to call | Required |
| `dependencies` | List[str] | List of step IDs that must complete first | [] |
| `parameters` | Dict | Parameters to pass to the operation | {} |
| `timeout` | float | Maximum execution time in seconds | None |
| `retry_count` | int | Number of retry attempts | 3 |
| `retry_delay` | float | Delay between retries in seconds | 1.0 |
| `critical` | bool | Whether step failure should stop workflow | True |
| `parallel_group` | str | Group for parallel execution | None |
| `priority` | int | Priority for priority-based execution | 0 |

### Dependency Management

Steps can depend on other steps using the `dependencies` field:

```python
{
    "name": "step_c",
    "dependencies": ["step_a", "step_b"],  # Runs after both step_a and step_b complete
    # ... other parameters
}
```

The orchestrator automatically handles:
- Topological sorting of steps based on dependencies
- Circular dependency detection
- Parallel execution of independent steps

### Parallel Execution

Steps can be grouped for parallel execution:

```python
[
    {
        "name": "analyze_performance",
        "parallel_group": "analysis",
        "dependencies": ["setup"],
    },
    {
        "name": "analyze_quality",
        "parallel_group": "analysis",
        "dependencies": ["setup"],
    },
    {
        "name": "generate_improvements",
        "dependencies": ["analyze_performance", "analyze_quality"],
    },
]
```

## Event Integration

The orchestration system publishes events throughout execution:

### Event Types
- **State Changes**: Workflow state transitions
- **Progress Updates**: Iteration and step progress
- **Error Events**: Failures and recovery attempts
- **Resource Alerts**: Threshold violations
- **Pipeline Stage Events**: Stage start/completion/failure

### Event Handling

```python
from evoseal.core.events import event_bus

@event_bus.subscribe("orchestration.checkpoint_created")
async def on_checkpoint_created(event):
    print(f"Checkpoint created: {event.data['checkpoint_id']}")

@event_bus.subscribe("orchestration.recovery_initiated")
async def on_recovery_initiated(event):
    print(f"Recovery initiated: {event.data['error_type']}")
```

## Monitoring and Metrics

### Workflow Status

```python
status = orchestrator.get_workflow_status()
# Returns:
{
    "state": "running",
    "execution_context": {
        "workflow_id": "workflow_001",
        "current_iteration": 3,
        "total_iterations": 10,
        "current_stage": "generate",
    },
    "resource_usage": {
        "memory_percent": 65.2,
        "cpu_percent": 45.8,
        "disk_percent": 78.1,
    },
    "active_alerts": [],
    "checkpoint_count": 2,
    "recovery_attempts": 0,
}
```

### Resource Statistics

```python
resource_stats = orchestrator.resource_monitor.get_resource_statistics()
# Returns detailed resource usage statistics
```

### Recovery Statistics

```python
recovery_stats = orchestrator.recovery_manager.get_recovery_statistics()
# Returns recovery attempt history and success rates
```

### Checkpoint Statistics

```python
checkpoint_stats = orchestrator.checkpoint_manager.get_checkpoint_statistics()
# Returns checkpoint counts, types, and storage information
```

## Error Handling and Recovery

### Recovery Strategies

The system provides multiple recovery strategies that are applied in sequence:

1. **Retry with Backoff**: Simple retry with configurable delays
2. **Checkpoint Rollback**: Restore from previous successful state
3. **Component Restart**: Restart failed components
4. **State Validation**: Verify and repair workflow state
5. **Custom Actions**: User-defined recovery procedures

### Custom Recovery Actions

```python
async def custom_recovery_action(error, execution_context, iteration, step_id):
    """Custom recovery action."""
    logger.info(f"Attempting custom recovery for {error}")
    # Implement custom recovery logic
    return True  # Return True if recovery successful

# Add to recovery strategy
recovery_strategy.custom_recovery_actions.append(custom_recovery_action)
```

### Error Types and Handling

| Error Type | Recovery Strategy | Description |
|------------|-------------------|-------------|
| `TimeoutError` | Retry with backoff | Step execution timeout |
| `ConnectionError` | Component restart | Network/service connection issues |
| `MemoryError` | Checkpoint rollback | Out of memory conditions |
| `RuntimeError` | Custom actions | General runtime errors |
| `ValidationError` | State validation | Data validation failures |

## Best Practices

### Workflow Design
1. **Define Clear Dependencies**: Ensure proper step ordering
2. **Set Appropriate Timeouts**: Prevent hanging operations
3. **Mark Critical Steps**: Identify steps that must succeed
4. **Use Parallel Groups**: Optimize execution time
5. **Configure Retries**: Handle transient failures

### Resource Management
1. **Set Conservative Thresholds**: Avoid resource exhaustion
2. **Monitor Long-Running Workflows**: Track resource trends
3. **Clean Up Checkpoints**: Manage storage usage
4. **Use Appropriate Intervals**: Balance monitoring overhead

### Error Handling
1. **Implement Custom Recovery**: Handle domain-specific errors
2. **Test Recovery Scenarios**: Verify recovery mechanisms
3. **Monitor Recovery Success**: Track recovery effectiveness
4. **Log Recovery Actions**: Maintain audit trail

### Performance Optimization
1. **Choose Appropriate Strategy**: Sequential vs parallel execution
2. **Optimize Step Dependencies**: Minimize blocking
3. **Tune Checkpoint Intervals**: Balance safety and performance
4. **Monitor Resource Usage**: Identify bottlenecks

## Integration with EVOSEAL Pipeline

The orchestration system integrates seamlessly with the EVOSEAL evolution pipeline:

```python
from evoseal.core.evolution_pipeline import EvolutionPipeline
from evoseal.core.orchestration import WorkflowOrchestrator

# Create pipeline
pipeline = EvolutionPipeline(config)

# Create orchestrator
orchestrator = WorkflowOrchestrator()

# Define evolution workflow
workflow_config = {
    "workflow_id": "evolution_001",
    "iterations": 20,
    "steps": [
        {
            "name": "analyze",
            "component": "_analyze_current_version",
            "operation": "__call__",
        },
        {
            "name": "generate",
            "component": "_generate_improvements",
            "operation": "__call__",
            "dependencies": ["analyze"],
        },
        {
            "name": "adapt",
            "component": "_adapt_improvements",
            "operation": "__call__",
            "dependencies": ["generate"],
        },
        {
            "name": "evaluate",
            "component": "_evaluate_version",
            "operation": "__call__",
            "dependencies": ["adapt"],
        },
        {
            "name": "validate",
            "component": "_validate_improvement",
            "operation": "__call__",
            "dependencies": ["evaluate"],
        },
    ],
}

# Execute orchestrated evolution
await orchestrator.initialize_workflow(workflow_config)
result = await orchestrator.execute_workflow(pipeline)
```

## Troubleshooting

### Common Issues

#### Workflow Fails to Initialize
- Check workflow step configuration
- Verify component and operation names
- Validate dependencies

#### Steps Fail Repeatedly
- Check component availability
- Verify parameters
- Review timeout settings
- Check resource constraints

#### Recovery Fails
- Review recovery strategy configuration
- Check checkpoint availability
- Verify component restart capability
- Review custom recovery actions

#### High Resource Usage
- Adjust resource thresholds
- Increase monitoring frequency
- Review step resource requirements
- Consider parallel execution limits

### Debugging

Enable detailed logging:

```python
import logging
logging.getLogger('evoseal.core.orchestration').setLevel(logging.DEBUG)
```

Check orchestrator status:

```python
status = orchestrator.get_workflow_status()
print(f"State: {status['state']}")
print(f"Active alerts: {status['active_alerts']}")
```

Review checkpoint history:

```python
checkpoints = orchestrator.checkpoint_manager.list_checkpoints()
for cp in checkpoints:
    print(f"{cp.checkpoint_id}: {cp.checkpoint_type.value} - {cp.timestamp}")
```

## API Reference

### WorkflowOrchestrator

Main orchestrator class for workflow management.

#### Methods

- `__init__(workspace_dir, checkpoint_interval, execution_strategy, recovery_strategy, resource_thresholds, monitoring_interval)`
- `initialize_workflow(workflow_config) -> bool`
- `execute_workflow(pipeline_instance, resume_from_checkpoint=None) -> WorkflowResult`
- `pause_workflow() -> bool`
- `resume_workflow() -> bool`
- `cancel_workflow() -> bool`
- `get_workflow_status() -> Dict[str, Any]`

### CheckpointManager

Manages workflow checkpoints and state persistence.

#### Methods

- `create_checkpoint(checkpoint_type, execution_context, workflow_steps, step_results, state, resource_usage, custom_metadata=None) -> str`
- `get_checkpoint(checkpoint_id) -> Optional[Dict[str, Any]]`
- `list_checkpoints(checkpoint_type=None, experiment_id=None, limit=None) -> List[CheckpointMetadata]`
- `delete_checkpoint(checkpoint_id) -> bool`
- `cleanup_old_checkpoints(max_age_days=30, max_count=100, keep_milestone=True) -> int`

### RecoveryManager

Handles error recovery and retry strategies.

#### Methods

- `attempt_recovery(error, execution_context, iteration, step_id=None) -> bool`
- `get_recovery_statistics() -> Dict[str, Any]`
- `add_custom_recovery_action(action) -> None`
- `remove_custom_recovery_action(action) -> bool`

### ResourceMonitor

Monitors system resources and provides alerts.

#### Methods

- `start_monitoring() -> None`
- `stop_monitoring() -> None`
- `get_current_usage() -> Optional[ResourceSnapshot]`
- `get_usage_history(hours=1) -> List[ResourceSnapshot]`
- `get_active_alerts() -> List[ResourceAlert]`
- `add_alert_callback(callback) -> None`

## Conclusion

The EVOSEAL Workflow Orchestration System provides a comprehensive solution for managing complex evolution workflows with robust error handling, resource monitoring, and state management. Its modular architecture and flexible configuration options make it suitable for a wide range of evolution scenarios, from simple sequential workflows to complex parallel processing pipelines.

The system's emphasis on reliability, observability, and recoverability ensures that long-running evolution processes can complete successfully even in challenging environments with resource constraints and intermittent failures.
