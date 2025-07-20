# EVOSEAL Component Integration System

This module provides a comprehensive integration system for orchestrating external components (DGM, OpenEvolve, SEAL (Self-Adapting Language Models)) within the EVOSEAL evolution pipeline.

## Overview

The integration system consists of several key components:

- **Base Adapter**: Abstract base class for all component adapters
- **Component Adapters**: Specific implementations for DGM, OpenEvolve, and SEAL (Self-Adapting Language Models)
- **Integration Orchestrator**: Central coordinator for all components
- **Evolution Pipeline Integration**: Seamless integration with the main pipeline

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Evolution Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│                Integration Orchestrator                     │
├─────────────────┬─────────────────┬─────────────────────────┤
│   DGM Adapter   │ OpenEvolve      │     SEAL (Self-Adapting Language Models) Adapter        │
│                 │ Adapter         │                         │
├─────────────────┼─────────────────┼─────────────────────────┤
│   DGM Module    │ OpenEvolve      │     SEAL (Self-Adapting Language Models) Interface      │
│                 │ Module          │                         │
└─────────────────┴─────────────────┴─────────────────────────┘
```

## Component Adapters

### DGM Adapter

The DGM adapter provides integration with the Dynamic Generation Management system:

**Supported Operations:**
- `advance_generation`: Advance to the next generation
- `choose_parents`: Select parents for reproduction
- `mutate`: Perform mutation on a parent
- `crossover`: Perform crossover between parents
- `get_fitness`: Get fitness metrics for a run
- `get_archive`: Get the current archive
- `update_archive`: Update the archive with new runs

**Configuration:**
```python
dgm_config = {
    "output_dir": "/path/to/dgm/output",
    "prevrun_dir": "/path/to/previous/runs",  # Optional
    "polyglot": False
}
```

### OpenEvolve Adapter

The OpenEvolve adapter provides integration with the OpenEvolve code evolution system:

**Supported Operations:**
- `evolve`: Run code evolution
- `optimize`: Optimize existing code
- `test`: Run tests on evolved code
- `evaluate`: Evaluate code quality/performance
- `generate`: Generate new code
- `mutate`: Apply mutations to code
- `crossover`: Perform crossover between code variants
- `validate`: Validate evolved code

**Configuration:**
```python
openevolve_config = {
    "openevolve_path": "/path/to/openevolve",  # Auto-detected if not provided
    "working_dir": "/path/to/working/directory",
    "python_executable": "python3",
    "environment": {"ENV_VAR": "value"}  # Optional environment variables
}
```

### SEAL (Self-Adapting Language Models) Adapter

The SEAL (Self-Adapting Language Models) adapter provides integration with Self-Adapting Language Models:

**Supported Operations:**
- `submit_prompt`: Submit a prompt to SEAL (Self-Adapting Language Models)
- `batch_submit`: Submit multiple prompts
- `analyze_code`: Analyze code using SEAL (Self-Adapting Language Models)
- `generate_code`: Generate code using SEAL (Self-Adapting Language Models)
- `improve_code`: Improve existing code using SEAL (Self-Adapting Language Models)
- `explain_code`: Get code explanations from SEAL (Self-Adapting Language Models)
- `review_code`: Get code reviews from SEAL (Self-Adapting Language Models)
- `optimize_prompt`: Optimize prompt for better results

**Configuration:**
```python
seal_config = {
    "provider_type": "default",  # or custom provider
    "provider_config": {},
    "rate_limit_per_sec": 1.0,
    "max_retries": 3,
    "retry_delay": 1.0
}
```

## Usage Examples

### Basic Integration

```python
from evoseal.integration import create_integration_orchestrator, ComponentType

# Create orchestrator with component configurations
orchestrator = create_integration_orchestrator(
    dgm_config={"output_dir": "/tmp/dgm"},
    seal_config={"provider_type": "default"}
)

# Initialize and start components
await orchestrator.initialize(orchestrator._component_configs)
await orchestrator.start()

# Execute component operations
result = await orchestrator.execute_component_operation(
    ComponentType.SEAL (Self-Adapting Language Models),
    "analyze_code",
    "def hello(): return 'world'"
)

# Stop components
await orchestrator.stop()
```

### Evolution Pipeline Integration

```python
from evoseal.core.evolution_pipeline import EvolutionPipeline, EvolutionConfig

# Create configuration with component configs
config = EvolutionConfig(
    dgm_config={"output_dir": "/tmp/dgm"},
    seal_config={"provider_type": "default"}
)

# Create and initialize pipeline
pipeline = EvolutionPipeline(config)
await pipeline.initialize_components()
await pipeline.start_components()

# Execute evolution workflow
workflow_config = {
    "workflow_id": "example",
    "dgm_config": {"selfimprove_size": 2},
    "seal_config": {"code": "def example(): pass"}
}
result = await pipeline.execute_evolution_workflow(workflow_config)

# Stop components
await pipeline.stop_components()
```

### Parallel Operations

```python
# Define multiple operations
operations = [
    {
        "component_type": ComponentType.SEAL (Self-Adapting Language Models),
        "operation": "analyze_code",
        "data": "code_sample_1"
    },
    {
        "component_type": ComponentType.SEAL (Self-Adapting Language Models),
        "operation": "analyze_code",
        "data": "code_sample_2"
    }
]

# Execute in parallel
results = await orchestrator.execute_parallel_operations(operations)
```

## Component Lifecycle

All components follow a standard lifecycle:

1. **Uninitialized**: Component created but not configured
2. **Initializing**: Component is being initialized
3. **Ready**: Component initialized and ready to start
4. **Running**: Component is active and processing requests
5. **Paused**: Component is temporarily paused
6. **Stopped**: Component has been stopped
7. **Error**: Component encountered an error

## Configuration Management

Components can be configured through:

1. **Direct Configuration**: Pass config dictionaries to factory functions
2. **Evolution Config**: Use EvolutionConfig class for pipeline integration
3. **Runtime Updates**: Update configuration during runtime

## Error Handling

The integration system provides comprehensive error handling:

- **Component-level**: Each adapter handles its own errors
- **Operation-level**: Individual operations return success/failure status
- **Orchestrator-level**: Central error coordination and logging
- **Pipeline-level**: Integration with pipeline error handling

## Monitoring and Metrics

### Component Status

```python
# Get status of all components
status = orchestrator.get_all_status()
for component_type, component_status in status.items():
    print(f"{component_type.value}: {component_status.state.value}")
```

### Component Metrics

```python
# Get metrics from all components
metrics = await orchestrator.get_all_metrics()
for component_type, component_metrics in metrics.items():
    print(f"{component_type.value}: {component_metrics}")
```

## Extending the System

### Creating Custom Adapters

To create a custom component adapter:

1. Inherit from `BaseComponentAdapter`
2. Implement required abstract methods
3. Define component-specific operations
4. Register with the component manager

```python
from evoseal.integration.base_adapter import BaseComponentAdapter, ComponentType

class CustomAdapter(BaseComponentAdapter):
    async def _initialize_impl(self) -> bool:
        # Initialize your component
        return True

    async def _start_impl(self) -> bool:
        # Start your component
        return True

    async def _stop_impl(self) -> bool:
        # Stop your component
        return True

    async def execute(self, operation: str, data: Any = None, **kwargs) -> ComponentResult:
        # Handle component operations
        pass

    async def get_metrics(self) -> Dict[str, Any]:
        # Return component metrics
        return {}
```

### Adding Custom Providers

For SEAL (Self-Adapting Language Models), you can add custom providers:

```python
class CustomSEALProvider:
    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str:
        # Your custom implementation
        pass

    async def parse_response(self, response: str) -> Any:
        # Your custom parsing logic
        pass

# Use with SEAL (Self-Adapting Language Models) adapter
seal_config = {
    "provider_type": "custom",
    "provider_class": CustomSEALProvider,
    "provider_config": {"api_key": "your_key"}  # pragma: allowlist secret
}
```

## Best Practices

1. **Always initialize components before starting them**
2. **Handle component failures gracefully**
3. **Use appropriate rate limits for external services**
4. **Monitor component health and metrics**
5. **Clean up resources by stopping components**
6. **Use parallel operations for independent tasks**
7. **Configure appropriate timeouts and retries**

## Troubleshooting

### Common Issues

1. **Component initialization fails**
   - Check configuration parameters
   - Verify external dependencies are available
   - Check file permissions and paths

2. **Operations timeout**
   - Increase timeout values in configuration
   - Check network connectivity for external services
   - Monitor system resources

3. **Rate limiting errors**
   - Reduce rate limits in configuration
   - Implement exponential backoff
   - Use batch operations where possible

### Debugging

Enable debug logging to get detailed information:

```python
import logging
logging.getLogger('evoseal.integration').setLevel(logging.DEBUG)
```

## Future Enhancements

- Support for additional component types
- Advanced workflow orchestration
- Component health checks and auto-recovery
- Distributed component execution
- Enhanced monitoring and observability
- Configuration validation and schema support
