#!/usr/bin/env python3
"""
EVOSEAL Integration Example

This example demonstrates how to use the new component integration system
to orchestrate DGM, OpenEvolve, and SEAL components in an evolution pipeline.
"""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def main():
    """Main example function."""
    try:
        # Import EVOSEAL components
        from evoseal.core.evolution_pipeline import EvolutionConfig, EvolutionPipeline
        from evoseal.integration import (
            ComponentType,
            IntegrationOrchestrator,
            create_integration_orchestrator,
        )

        logger.info("Starting EVOSEAL Integration Example")

        # Example 1: Basic Component Integration
        await example_basic_integration()

        # Example 2: Evolution Pipeline with Components
        await example_evolution_pipeline()

        # Example 3: Parallel Component Operations
        await example_parallel_operations()

        logger.info("All examples completed successfully!")

    except Exception:
        logger.exception("Error in main example")
        raise


async def example_basic_integration():
    """Example 1: Basic component integration and lifecycle management."""
    logger.info("\n=== Example 1: Basic Component Integration ===")

    # Create component configurations
    base_dir = Path(tempfile.gettempdir()) / "evoseal_example"  # nosec B108
    dgm_config = {"output_dir": str(base_dir / "dgm_output"), "polyglot": False}

    openevolve_config = {
        "working_dir": str(base_dir / "openevolve"),
        "python_executable": "python3",
    }

    seal_config = {
        "provider_type": "default",
        "rate_limit_per_sec": 2.0,
        "max_retries": 3,
    }

    # Create integration orchestrator
    orchestrator = create_integration_orchestrator(
        dgm_config=dgm_config,
        openevolve_config=openevolve_config,
        seal_config=seal_config,
    )

    try:
        # Initialize components
        logger.info("Initializing components...")
        success = await orchestrator.initialize(orchestrator._component_configs)
        if not success:
            logger.error("Failed to initialize components")
            return

        # Start components
        logger.info("Starting components...")
        success = await orchestrator.start()
        if not success:
            logger.error("Failed to start components")
            return

        # Get component status
        logger.info("Component status:")
        status = orchestrator.get_all_status()
        for component_type, component_status in status.items():
            logger.info(
                f"  {component_type.value}: {component_status.state.value} - {component_status.message}"
            )

        # Get component metrics
        logger.info("Component metrics:")
        metrics = await orchestrator.get_all_metrics()
        for component_type, component_metrics in metrics.items():
            logger.info(
                f"  {component_type.value}: {json.dumps(component_metrics, indent=2)}"
            )

        # Test individual component operations
        await test_component_operations(orchestrator)

    finally:
        # Stop components
        logger.info("Stopping components...")
        await orchestrator.stop()


async def test_component_operations(orchestrator):
    """Test individual component operations."""
    logger.info("\n--- Testing Component Operations ---")

    # Test DGM operations
    if orchestrator.get_component(ComponentType.DGM):
        logger.info("Testing DGM operations...")

        # Get current archive
        result = await orchestrator.execute_component_operation(
            ComponentType.DGM, "get_archive"
        )
        logger.info(f"DGM Archive: {result.data if result.success else result.error}")

        # Get current generation
        result = await orchestrator.execute_component_operation(
            ComponentType.DGM, "get_generation"
        )
        logger.info(
            f"DGM Generation: {result.data if result.success else result.error}"
        )

    # Test SEAL (Self-Adapting Language Models) operations
    if orchestrator.get_component(ComponentType.SEAL):
        logger.info("Testing SEAL (Self-Adapting Language Models) operations...")

        # Submit a test prompt
        result = await orchestrator.execute_component_operation(
            ComponentType.SEAL,
            "submit_prompt",
            "Hello, SEAL (Self-Adapting Language Models)! Please analyze this simple greeting.",
        )
        logger.info(
            f"SEAL (Self-Adapting Language Models) Response: {result.data if result.success else result.error}"
        )

        # Analyze some sample code
        sample_code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
        result = await orchestrator.execute_component_operation(
            ComponentType.SEAL, "analyze_code", sample_code
        )
        logger.info(
            f"SEAL (Self-Adapting Language Models) Code Analysis: {result.data if result.success else result.error}"
        )

    # Test OpenEvolve operations (if available)
    if orchestrator.get_component(ComponentType.OPENEVOLVE):
        logger.info("Testing OpenEvolve operations...")

        # Test basic command
        result = await orchestrator.execute_component_operation(
            ComponentType.OPENEVOLVE, "run_command", ["--help"]
        )
        logger.info(
            f"OpenEvolve Help: {result.data if result.success else result.error}"
        )


async def example_evolution_pipeline():
    """Example 2: Using the evolution pipeline with integrated components."""
    logger.info("\n=== Example 2: Evolution Pipeline with Components ===")

    # Create evolution configuration with component configs
    base_dir = Path(tempfile.gettempdir()) / "evoseal_example"  # nosec B108
    config = EvolutionConfig(
        dgm_config={"output_dir": str(base_dir / "pipeline_dgm"), "polyglot": False},
        seal_config={"provider_type": "default", "rate_limit_per_sec": 1.0},
        # OpenEvolve config can be added when the component is available
    )

    # Create evolution pipeline
    pipeline = EvolutionPipeline(config)

    try:
        # Initialize components
        logger.info("Initializing pipeline components...")
        success = await pipeline.initialize_components()
        if not success:
            logger.error("Failed to initialize pipeline components")
            return

        # Start components
        logger.info("Starting pipeline components...")
        success = await pipeline.start_components()
        if not success:
            logger.error("Failed to start pipeline components")
            return

        # Get component status through pipeline
        logger.info("Pipeline component status:")
        status = pipeline.get_component_status()
        for component, component_status in status.items():
            logger.info(f"  {component}: {component_status}")

        # Execute a sample evolution workflow
        workflow_config = {
            "workflow_id": "example_workflow",
            "dgm_config": {"selfimprove_size": 2},
            "dgm_params": {"method": "random"},
            "seal_config": {"code": "def hello(): return 'world'"},
            "seal_params": {"analysis_type": "general"},
        }

        logger.info("Executing evolution workflow...")
        result = await pipeline.execute_evolution_workflow(workflow_config)
        logger.info(f"Workflow result: {json.dumps(result, indent=2)}")

    finally:
        # Stop components
        logger.info("Stopping pipeline components...")
        await pipeline.stop_components()


async def example_parallel_operations():
    """Example 3: Executing parallel component operations."""
    logger.info("\n=== Example 3: Parallel Component Operations ===")

    # Create a simple orchestrator
    orchestrator = create_integration_orchestrator(
        seal_config={
            "provider_type": "default",
            "rate_limit_per_sec": 5.0,  # Higher rate limit for parallel ops
        }
    )

    try:
        # Initialize and start
        await orchestrator.initialize(orchestrator._component_configs)
        await orchestrator.start()

        # Define parallel operations
        operations = [
            {
                "component_type": ComponentType.SEAL,
                "operation": "submit_prompt",
                "data": "Analyze the performance of bubble sort algorithm.",
            },
            {
                "component_type": ComponentType.SEAL,
                "operation": "submit_prompt",
                "data": "Explain the concept of recursion in programming.",
            },
            {
                "component_type": ComponentType.SEAL,
                "operation": "analyze_code",
                "data": "def quicksort(arr): return arr if len(arr) <= 1 else quicksort([x for x in arr[1:] if x < arr[0]]) + [arr[0]] + quicksort([x for x in arr[1:] if x >= arr[0]])",
            },
        ]

        # Execute operations in parallel
        logger.info("Executing parallel operations...")
        results = await orchestrator.execute_parallel_operations(operations)

        # Display results
        for i, result in enumerate(results):
            logger.info(f"Operation {i+1}: {'Success' if result.success else 'Failed'}")
            if result.success:
                logger.info(f"  Data: {str(result.data)[:100]}...")
                logger.info(f"  Execution time: {result.execution_time:.2f}s")
            else:
                logger.info(f"  Error: {result.error}")

    finally:
        await orchestrator.stop()


def create_example_directories():
    """Create necessary directories for the example."""
    # Use system temp directory for security  # nosec B108
    base_dir = Path(tempfile.gettempdir()) / "evoseal_example"
    directories = [
        base_dir / "dgm_output",
        base_dir / "openevolve",
        base_dir / "pipeline_dgm",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    return base_dir


if __name__ == "__main__":
    # Create example directories
    base_dir = create_example_directories()
    print(f"Using temporary directory: {base_dir}")

    # Run the example
    asyncio.run(main())
