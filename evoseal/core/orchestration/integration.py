"""
Integration utilities for workflow orchestration with EVOSEAL pipeline.

Provides helper functions and classes to integrate the orchestration system
with existing EVOSEAL components and workflows.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from evoseal.core.events import event_bus

from .orchestrator import WorkflowOrchestrator
from .types import ExecutionStrategy, OrchestrationState

logger = logging.getLogger(__name__)


def create_evolution_workflow_config(
    workflow_id: str,
    iterations: int = 10,
    experiment_id: Optional[str] = None,
    execution_strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL,
    custom_steps: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a standard evolution workflow configuration.

    Args:
        workflow_id: Unique identifier for the workflow
        iterations: Number of evolution iterations to run
        experiment_id: Optional experiment ID for tracking
        execution_strategy: Execution strategy to use
        custom_steps: Optional custom workflow steps

    Returns:
        Workflow configuration dictionary
    """
    if custom_steps:
        steps = custom_steps
    else:
        # Standard EVOSEAL evolution pipeline steps
        steps = [
            {
                "name": "analyze",
                "component": "_analyze_current_version",
                "operation": "__call__",
                "parameters": {},
                "critical": True,
                "retry_count": 2,
                "timeout": 300.0,
            },
            {
                "name": "generate",
                "component": "_generate_improvements",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["analyze"],
                "critical": True,
                "retry_count": 3,
                "retry_delay": 2.0,
            },
            {
                "name": "adapt",
                "component": "_adapt_improvements",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["generate"],
                "critical": True,
                "retry_count": 2,
            },
            {
                "name": "evaluate",
                "component": "_evaluate_version",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["adapt"],
                "critical": True,
                "retry_count": 2,
                "timeout": 600.0,
            },
            {
                "name": "validate",
                "component": "_validate_improvement",
                "operation": "__call__",
                "parameters": {},
                "dependencies": ["evaluate"],
                "critical": True,
                "retry_count": 1,
            },
        ]

    return {
        "workflow_id": workflow_id,
        "experiment_id": experiment_id,
        "iterations": iterations,
        "execution_strategy": execution_strategy.value,
        "steps": steps,
        "resource_limits": {
            "max_memory_gb": 8.0,
            "max_cpu_percent": 90.0,
            "max_execution_time_hours": 24.0,
        },
        "custom_context": {
            "pipeline_type": "evolution",
            "created_by": "evoseal_integration",
        },
    }


def create_parallel_evolution_workflow_config(
    workflow_id: str,
    iterations: int = 10,
    experiment_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a parallel evolution workflow configuration.

    Args:
        workflow_id: Unique identifier for the workflow
        iterations: Number of evolution iterations to run
        experiment_id: Optional experiment ID for tracking

    Returns:
        Parallel workflow configuration dictionary
    """
    steps = [
        {
            "name": "analyze",
            "component": "_analyze_current_version",
            "operation": "__call__",
            "parameters": {},
            "critical": True,
            "retry_count": 2,
        },
        # Parallel generation and evaluation of current version
        {
            "name": "generate",
            "component": "_generate_improvements",
            "operation": "__call__",
            "parameters": {},
            "dependencies": ["analyze"],
            "parallel_group": "generation",
            "critical": True,
            "retry_count": 3,
        },
        {
            "name": "evaluate_baseline",
            "component": "_evaluate_version",
            "operation": "__call__",
            "parameters": {"baseline": True},
            "dependencies": ["analyze"],
            "parallel_group": "evaluation",
            "critical": False,  # Non-critical for parallel execution
            "retry_count": 2,
        },
        # Adaptation depends on generation
        {
            "name": "adapt",
            "component": "_adapt_improvements",
            "operation": "__call__",
            "parameters": {},
            "dependencies": ["generate"],
            "critical": True,
            "retry_count": 2,
        },
        # Final evaluation and validation
        {
            "name": "evaluate",
            "component": "_evaluate_version",
            "operation": "__call__",
            "parameters": {},
            "dependencies": ["adapt"],
            "critical": True,
            "retry_count": 2,
        },
        {
            "name": "validate",
            "component": "_validate_improvement",
            "operation": "__call__",
            "parameters": {},
            "dependencies": ["evaluate", "evaluate_baseline"],
            "critical": True,
            "retry_count": 1,
        },
    ]

    return {
        "workflow_id": workflow_id,
        "experiment_id": experiment_id,
        "iterations": iterations,
        "execution_strategy": ExecutionStrategy.PARALLEL.value,
        "steps": steps,
        "resource_limits": {
            "max_memory_gb": 12.0,  # Higher for parallel execution
            "max_cpu_percent": 95.0,
            "max_execution_time_hours": 48.0,
        },
        "custom_context": {
            "pipeline_type": "parallel_evolution",
            "created_by": "evoseal_integration",
        },
    }


class OrchestrationEventHandler:
    """Event handler for orchestration events."""

    def __init__(self):
        self.events_received = []
        self._register_handlers()

    def _register_handlers(self):
        """Register event handlers."""
        event_bus.subscribe("orchestration.*", self._on_orchestration_event)
        event_bus.subscribe("pipeline_stage.*", self._on_pipeline_stage_event)
        event_bus.subscribe("progress_update", self._on_progress_event)
        event_bus.subscribe("error", self._on_error_event)

    async def _on_orchestration_event(self, event):
        """Handle orchestration events."""
        self.events_received.append(
            {
                "type": "orchestration",
                "event_type": event.event_type,
                "data": event.data,
                "timestamp": event.timestamp,
            }
        )
        logger.info(f"Orchestration event: {event.event_type}")

    async def _on_pipeline_stage_event(self, event):
        """Handle pipeline stage events."""
        self.events_received.append(
            {
                "type": "pipeline_stage",
                "event_type": event.event_type,
                "data": event.data,
                "timestamp": event.timestamp,
            }
        )
        logger.info(f"Pipeline stage event: {event.event_type}")

    async def _on_progress_event(self, event):
        """Handle progress events."""
        self.events_received.append(
            {
                "type": "progress",
                "event_type": event.event_type,
                "data": event.data,
                "timestamp": event.timestamp,
            }
        )

    async def _on_error_event(self, event):
        """Handle error events."""
        self.events_received.append(
            {
                "type": "error",
                "event_type": event.event_type,
                "data": event.data,
                "timestamp": event.timestamp,
            }
        )
        logger.error(f"Error event: {event.data.get('error_message', 'Unknown error')}")

    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Get events filtered by type."""
        return [event for event in self.events_received if event["type"] == event_type]

    def clear_events(self):
        """Clear all received events."""
        self.events_received.clear()


async def run_orchestrated_evolution(
    pipeline_instance: Any,
    workflow_config: Dict[str, Any],
    orchestrator: Optional[WorkflowOrchestrator] = None,
    event_handler: Optional[OrchestrationEventHandler] = None,
) -> Dict[str, Any]:
    """Run an orchestrated evolution workflow.

    Args:
        pipeline_instance: Instance of the evolution pipeline
        workflow_config: Workflow configuration
        orchestrator: Optional orchestrator instance (creates new if None)
        event_handler: Optional event handler for monitoring

    Returns:
        Dictionary with execution results and statistics
    """
    # Create orchestrator if not provided
    if orchestrator is None:
        orchestrator = WorkflowOrchestrator(
            workspace_dir=f".evoseal_{workflow_config['workflow_id']}",
            checkpoint_interval=5,
            execution_strategy=ExecutionStrategy(
                workflow_config.get("execution_strategy", "sequential")
            ),
        )

    # Create event handler if not provided
    if event_handler is None:
        event_handler = OrchestrationEventHandler()

    try:
        # Initialize workflow
        logger.info(f"Initializing workflow: {workflow_config['workflow_id']}")
        success = await orchestrator.initialize_workflow(workflow_config)

        if not success:
            raise RuntimeError("Failed to initialize workflow")

        # Execute workflow
        logger.info("Starting orchestrated evolution execution")
        result = await orchestrator.execute_workflow(pipeline_instance)

        # Collect statistics
        orchestration_events = event_handler.get_events_by_type("orchestration")
        pipeline_events = event_handler.get_events_by_type("pipeline_stage")
        progress_events = event_handler.get_events_by_type("progress")
        error_events = event_handler.get_events_by_type("error")

        # Get final status
        final_status = orchestrator.get_workflow_status()

        # Get resource statistics
        resource_stats = orchestrator.resource_monitor.get_resource_statistics()

        # Get recovery statistics
        recovery_stats = orchestrator.recovery_manager.get_recovery_statistics()

        # Get checkpoint statistics
        checkpoint_stats = orchestrator.checkpoint_manager.get_checkpoint_statistics()

        return {
            "workflow_result": result,
            "final_status": final_status,
            "statistics": {
                "orchestration_events": len(orchestration_events),
                "pipeline_events": len(pipeline_events),
                "progress_events": len(progress_events),
                "error_events": len(error_events),
                "resource_stats": resource_stats,
                "recovery_stats": recovery_stats,
                "checkpoint_stats": checkpoint_stats,
            },
            "events": {
                "orchestration": orchestration_events,
                "pipeline_stage": pipeline_events,
                "progress": progress_events,
                "errors": error_events,
            },
        }

    except Exception as e:
        logger.error(f"Orchestrated evolution failed: {e}")

        # Get error statistics
        error_events = event_handler.get_events_by_type("error")
        final_status = orchestrator.get_workflow_status()

        return {
            "workflow_result": None,
            "final_status": final_status,
            "error": str(e),
            "statistics": {
                "error_events": len(error_events),
            },
            "events": {
                "errors": error_events,
            },
        }


def validate_orchestration_setup() -> Dict[str, bool]:
    """Validate that the orchestration system is properly set up.

    Returns:
        Dictionary with validation results
    """
    validation_results = {}

    try:
        # Test orchestrator creation
        orchestrator = WorkflowOrchestrator(workspace_dir=".evoseal_validation_test")
        validation_results["orchestrator_creation"] = True
    except Exception as e:
        logger.error(f"Orchestrator creation failed: {e}")
        validation_results["orchestrator_creation"] = False

    try:
        # Test workflow config creation
        config = create_evolution_workflow_config("validation_test", iterations=1)
        validation_results["workflow_config_creation"] = True
    except Exception as e:
        logger.error(f"Workflow config creation failed: {e}")
        validation_results["workflow_config_creation"] = False

    try:
        # Test event handler creation
        event_handler = OrchestrationEventHandler()
        validation_results["event_handler_creation"] = True
    except Exception as e:
        logger.error(f"Event handler creation failed: {e}")
        validation_results["event_handler_creation"] = False

    try:
        # Test imports
        from .checkpoint_manager import CheckpointManager
        from .recovery_manager import RecoveryManager
        from .resource_monitor import ResourceMonitor

        validation_results["component_imports"] = True
    except Exception as e:
        logger.error(f"Component imports failed: {e}")
        validation_results["component_imports"] = False

    return validation_results


# Convenience functions for common orchestration patterns


async def run_simple_evolution(
    pipeline_instance: Any,
    workflow_id: str,
    iterations: int = 10,
    checkpoint_interval: int = 5,
) -> Dict[str, Any]:
    """Run a simple sequential evolution workflow.

    Args:
        pipeline_instance: Evolution pipeline instance
        workflow_id: Unique workflow identifier
        iterations: Number of iterations to run
        checkpoint_interval: Checkpoint interval

    Returns:
        Execution results
    """
    workflow_config = create_evolution_workflow_config(
        workflow_id=workflow_id,
        iterations=iterations,
        execution_strategy=ExecutionStrategy.SEQUENTIAL,
    )

    orchestrator = WorkflowOrchestrator(
        workspace_dir=f".evoseal_{workflow_id}",
        checkpoint_interval=checkpoint_interval,
        execution_strategy=ExecutionStrategy.SEQUENTIAL,
    )

    return await run_orchestrated_evolution(
        pipeline_instance=pipeline_instance,
        workflow_config=workflow_config,
        orchestrator=orchestrator,
    )


async def run_parallel_evolution(
    pipeline_instance: Any,
    workflow_id: str,
    iterations: int = 10,
    checkpoint_interval: int = 3,
) -> Dict[str, Any]:
    """Run a parallel evolution workflow.

    Args:
        pipeline_instance: Evolution pipeline instance
        workflow_id: Unique workflow identifier
        iterations: Number of iterations to run
        checkpoint_interval: Checkpoint interval

    Returns:
        Execution results
    """
    workflow_config = create_parallel_evolution_workflow_config(
        workflow_id=workflow_id,
        iterations=iterations,
    )

    orchestrator = WorkflowOrchestrator(
        workspace_dir=f".evoseal_{workflow_id}",
        checkpoint_interval=checkpoint_interval,
        execution_strategy=ExecutionStrategy.PARALLEL,
    )

    return await run_orchestrated_evolution(
        pipeline_instance=pipeline_instance,
        workflow_config=workflow_config,
        orchestrator=orchestrator,
    )
