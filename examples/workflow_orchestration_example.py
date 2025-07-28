"""
Workflow Orchestration Example

Demonstrates the comprehensive workflow orchestration system with checkpointing,
recovery, resource monitoring, and execution flow optimization.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

from evoseal.core.orchestration import (
    ExecutionStrategy,
    OrchestrationState,
    RecoveryStrategy,
    ResourceThresholds,
    WorkflowOrchestrator,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockPipeline:
    """Mock pipeline for demonstration purposes."""

    def __init__(self):
        self.iteration_count = 0
        self.failure_rate = 0.1  # 10% failure rate for demonstration

    async def analyze_current_version(self, **kwargs):
        """Mock analysis step."""
        await asyncio.sleep(1)  # Simulate work
        return {"analysis": "code quality: good", "suggestions": 3}

    async def generate_improvements(self, **kwargs):
        """Mock improvement generation step."""
        await asyncio.sleep(2)  # Simulate work

        # Simulate occasional failure
        if self.iteration_count % 7 == 0:  # Fail every 7th iteration
            raise RuntimeError("Generation service temporarily unavailable")

        return {"improvements": ["optimize loops", "reduce memory usage"], "count": 2}

    async def adapt_improvements(self, **kwargs):
        """Mock adaptation step."""
        await asyncio.sleep(1.5)  # Simulate work
        return {"adapted": True, "changes": 5}

    async def evaluate_version(self, **kwargs):
        """Mock evaluation step."""
        await asyncio.sleep(2.5)  # Simulate work

        # Simulate memory-intensive operation
        if self.iteration_count % 5 == 0:
            logger.info("Simulating memory-intensive evaluation")

        return {"score": 0.85, "improvements": True}

    async def validate_improvement(self, **kwargs):
        """Mock validation step."""
        await asyncio.sleep(1)  # Simulate work
        self.iteration_count += 1
        return {"valid": True, "confidence": 0.9}


async def demonstrate_basic_orchestration():
    """Demonstrate basic workflow orchestration."""
    print("\n=== Basic Workflow Orchestration Demo ===")

    # Create orchestrator
    orchestrator = WorkflowOrchestrator(
        workspace_dir=".evoseal_demo",
        checkpoint_interval=3,  # Checkpoint every 3 iterations
        execution_strategy=ExecutionStrategy.SEQUENTIAL,
    )

    # Define workflow configuration
    workflow_config = {
        "workflow_id": "demo_workflow_basic",
        "experiment_id": "exp_001",
        "iterations": 5,
        "steps": [
            {
                "name": "analyze",
                "component": "analyze_current_version",
                "operation": "__call__",
                "parameters": {},
                "critical": True,
                "retry_count": 2,
            },
            {
                "name": "generate",
                "component": "generate_improvements",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["analyze"],
                "critical": True,
                "retry_count": 3,
            },
            {
                "name": "adapt",
                "component": "adapt_improvements",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["generate"],
                "critical": True,
            },
            {
                "name": "evaluate",
                "component": "evaluate_version",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["adapt"],
                "critical": True,
            },
            {
                "name": "validate",
                "component": "validate_improvement",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["evaluate"],
                "critical": True,
            },
        ],
    }

    # Initialize workflow
    pipeline = MockPipeline()
    success = await orchestrator.initialize_workflow(workflow_config)

    if not success:
        print("Failed to initialize workflow")
        return

    print(f"Workflow initialized: {workflow_config['workflow_id']}")

    # Execute workflow
    try:
        result = await orchestrator.execute_workflow(pipeline)

        print("\nWorkflow completed!")
        print(f"- Total iterations: {len(result.iterations)}")
        print(f"- Successful iterations: {result.success_count}")
        print(f"- Failed iterations: {result.failure_count}")
        print(f"- Total execution time: {result.total_execution_time:.2f}s")
        print(f"- Checkpoints created: {result.checkpoints_created}")
        print(f"- Final state: {result.final_state.value}")

    except Exception as e:
        print(f"Workflow execution failed: {e}")

    # Show status
    status = orchestrator.get_workflow_status()
    print(f"\nFinal workflow status: {status['state']}")


async def demonstrate_recovery_orchestration():
    """Demonstrate workflow orchestration with recovery."""
    print("\n=== Recovery-Enabled Workflow Orchestration Demo ===")

    # Create recovery strategy
    recovery_strategy = RecoveryStrategy(
        max_retries=3,
        retry_delay=2.0,
        exponential_backoff=True,
        checkpoint_rollback=True,
        component_restart=True,
    )

    # Create orchestrator with recovery
    orchestrator = WorkflowOrchestrator(
        workspace_dir=".evoseal_demo_recovery",
        checkpoint_interval=2,  # More frequent checkpoints
        execution_strategy=ExecutionStrategy.ADAPTIVE,
        recovery_strategy=recovery_strategy,
    )

    # Define workflow with potential failures
    workflow_config = {
        "workflow_id": "demo_workflow_recovery",
        "experiment_id": "exp_002",
        "iterations": 10,  # More iterations to trigger failures
        "steps": [
            {
                "name": "analyze",
                "component": "analyze_current_version",
                "operation": "__call__",
                "parameters": {},
                "critical": True,
                "retry_count": 2,
                "timeout": 10.0,
            },
            {
                "name": "generate",
                "component": "generate_improvements",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["analyze"],
                "critical": True,
                "retry_count": 3,
                "retry_delay": 1.0,
            },
            {
                "name": "evaluate",
                "component": "evaluate_version",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["generate"],
                "critical": False,  # Non-critical step
            },
        ],
    }

    # Initialize and execute workflow
    pipeline = MockPipeline()
    success = await orchestrator.initialize_workflow(workflow_config)

    if success:
        print(f"Workflow with recovery initialized: {workflow_config['workflow_id']}")

        try:
            result = await orchestrator.execute_workflow(pipeline)

            print("\nRecovery-enabled workflow completed!")
            print(f"- Total iterations: {len(result.iterations)}")
            print(f"- Successful iterations: {result.success_count}")
            print(f"- Failed iterations: {result.failure_count}")
            print(f"- Total execution time: {result.total_execution_time:.2f}s")

            # Show recovery statistics
            recovery_stats = orchestrator.recovery_manager.get_recovery_statistics()
            print("\nRecovery Statistics:")
            print(f"- Total recovery attempts: {recovery_stats['total_attempts']}")
            print(f"- Successful recoveries: {recovery_stats['successful_attempts']}")
            print(f"- Recovery success rate: {recovery_stats['success_rate']:.1%}")

        except Exception as e:
            print(f"Workflow execution failed even with recovery: {e}")


async def demonstrate_parallel_orchestration():
    """Demonstrate parallel workflow orchestration."""
    print("\n=== Parallel Workflow Orchestration Demo ===")

    # Create orchestrator with parallel execution
    orchestrator = WorkflowOrchestrator(
        workspace_dir=".evoseal_demo_parallel",
        checkpoint_interval=3,
        execution_strategy=ExecutionStrategy.PARALLEL,
    )

    # Define workflow with parallel steps
    workflow_config = {
        "workflow_id": "demo_workflow_parallel",
        "experiment_id": "exp_003",
        "iterations": 3,
        "steps": [
            {
                "name": "analyze",
                "component": "analyze_current_version",
                "operation": "__call__",
                "parameters": {},
                "critical": True,
            },
            # These two steps can run in parallel after analyze
            {
                "name": "generate",
                "component": "generate_improvements",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["analyze"],
                "parallel_group": "generation",
            },
            {
                "name": "evaluate_current",
                "component": "evaluate_version",
                "operation": "__call__",
                "parameters": {"baseline": True},
                "dependencies": ["analyze"],
                "parallel_group": "evaluation",
            },
            # Final step depends on both parallel groups
            {
                "name": "validate",
                "component": "validate_improvement",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["generate", "evaluate_current"],
                "critical": True,
            },
        ],
    }

    # Initialize and execute workflow
    pipeline = MockPipeline()
    success = await orchestrator.initialize_workflow(workflow_config)

    if success:
        print(f"Parallel workflow initialized: {workflow_config['workflow_id']}")

        start_time = time.time()
        result = await orchestrator.execute_workflow(pipeline)
        total_time = time.time() - start_time

        print("\nParallel workflow completed!")
        print(f"- Total wall-clock time: {total_time:.2f}s")
        print(f"- Pipeline execution time: {result.total_execution_time:.2f}s")
        print(f"- Iterations completed: {len(result.iterations)}")


async def demonstrate_resource_monitoring():
    """Demonstrate resource monitoring integration."""
    print("\n=== Resource Monitoring Demo ===")

    # Create resource thresholds
    resource_thresholds = ResourceThresholds(
        memory_warning=0.6,  # Lower thresholds for demo
        memory_critical=0.8,
        cpu_warning=0.7,
        cpu_critical=0.9,
    )

    # Create orchestrator with resource monitoring
    orchestrator = WorkflowOrchestrator(
        workspace_dir=".evoseal_demo_resources",
        checkpoint_interval=2,
        execution_strategy=ExecutionStrategy.ADAPTIVE,
        resource_thresholds=resource_thresholds,
        monitoring_interval=5.0,  # Check every 5 seconds
    )

    # Simple workflow for resource monitoring
    workflow_config = {
        "workflow_id": "demo_workflow_resources",
        "experiment_id": "exp_004",
        "iterations": 5,
        "steps": [
            {
                "name": "evaluate",
                "component": "evaluate_version",
                "operation": "__call__",
                "parameters": {},
                "critical": True,
            },
        ],
    }

    # Initialize and execute workflow
    pipeline = MockPipeline()
    success = await orchestrator.initialize_workflow(workflow_config)

    if success:
        print(f"Resource-monitored workflow initialized: {workflow_config['workflow_id']}")

        # Let it run for a bit to collect resource data
        result = await orchestrator.execute_workflow(pipeline)

        print("\nResource-monitored workflow completed!")

        # Show resource statistics
        resource_stats = orchestrator.resource_monitor.get_resource_statistics()
        print("\nResource Statistics:")
        print(f"- Monitoring active: {resource_stats['monitoring_active']}")
        print(f"- Snapshots collected: {resource_stats['snapshots_collected']}")
        print(f"- Active alerts: {resource_stats['active_alerts']}")
        print(f"- Memory usage - Current: {resource_stats['memory_stats']['current']:.1f}%")
        print(f"- CPU usage - Current: {resource_stats['cpu_stats']['current']:.1f}%")

        # Show any alerts
        active_alerts = orchestrator.resource_monitor.get_active_alerts()
        if active_alerts:
            print("\nActive Resource Alerts:")
            for alert in active_alerts:
                print(f"- {alert.severity.upper()}: {alert.message}")


async def demonstrate_checkpoint_management():
    """Demonstrate checkpoint management."""
    print("\n=== Checkpoint Management Demo ===")

    # Create orchestrator
    orchestrator = WorkflowOrchestrator(
        workspace_dir=".evoseal_demo_checkpoints",
        checkpoint_interval=2,  # Frequent checkpoints
        execution_strategy=ExecutionStrategy.SEQUENTIAL,
    )

    # Simple workflow
    workflow_config = {
        "workflow_id": "demo_workflow_checkpoints",
        "experiment_id": "exp_005",
        "iterations": 6,
        "steps": [
            {
                "name": "analyze",
                "component": "analyze_current_version",
                "operation": "__call__",
                "parameters": {},
            },
            {
                "name": "generate",
                "component": "generate_improvements",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["analyze"],
            },
        ],
    }

    # Initialize and execute workflow
    pipeline = MockPipeline()
    success = await orchestrator.initialize_workflow(workflow_config)

    if success:
        print(f"Checkpoint demo workflow initialized: {workflow_config['workflow_id']}")

        result = await orchestrator.execute_workflow(pipeline)

        print("\nCheckpoint demo completed!")
        print(f"- Checkpoints created: {result.checkpoints_created}")

        # Show checkpoint statistics
        checkpoint_stats = orchestrator.checkpoint_manager.get_checkpoint_statistics()
        print("\nCheckpoint Statistics:")
        print(f"- Total checkpoints: {checkpoint_stats['total_count']}")
        print(f"- By type: {checkpoint_stats['by_type']}")
        print(f"- Total size: {checkpoint_stats['total_size_mb']} MB")

        # List recent checkpoints
        recent_checkpoints = orchestrator.checkpoint_manager.list_checkpoints(limit=3)
        print("\nRecent Checkpoints:")
        for cp in recent_checkpoints:
            print(f"- {cp.checkpoint_id}: {cp.checkpoint_type.value} at iteration {cp.iteration}")


async def main():
    """Run all orchestration demonstrations."""
    print("EVOSEAL Workflow Orchestration System Demo")
    print("=" * 50)

    try:
        # Run all demonstrations
        await demonstrate_basic_orchestration()
        await asyncio.sleep(1)  # Brief pause between demos

        await demonstrate_recovery_orchestration()
        await asyncio.sleep(1)

        await demonstrate_parallel_orchestration()
        await asyncio.sleep(1)

        await demonstrate_resource_monitoring()
        await asyncio.sleep(1)

        await demonstrate_checkpoint_management()

        print("\n" + "=" * 50)
        print("All workflow orchestration demonstrations completed!")

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
