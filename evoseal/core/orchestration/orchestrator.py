"""
Main Workflow Orchestrator

Core orchestrator that coordinates checkpointing, recovery, and resource monitoring
for comprehensive workflow execution management.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from evoseal.core.events import (
    create_error_event,
    create_progress_event,
    create_state_change_event,
    event_bus,
    publish_pipeline_stage_event,
)

from .checkpoint_manager import CheckpointManager, CheckpointType
from .recovery_manager import RecoveryManager, RecoveryStrategy
from .resource_monitor import ResourceMonitor, ResourceThresholds
from .types import (
    ExecutionContext,
    ExecutionStrategy,
    IterationResult,
    OrchestrationState,
    StepResult,
    WorkflowResult,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """
    Main workflow orchestrator for EVOSEAL pipeline.

    Coordinates checkpointing, recovery, resource monitoring, and execution
    flow optimization for comprehensive workflow management.
    """

    def __init__(
        self,
        workspace_dir: str = ".evoseal",
        checkpoint_interval: int = 5,
        execution_strategy: ExecutionStrategy = ExecutionStrategy.ADAPTIVE,
        recovery_strategy: Optional[RecoveryStrategy] = None,
        resource_thresholds: Optional[ResourceThresholds] = None,
        monitoring_interval: float = 30.0,
    ):
        """Initialize the workflow orchestrator.

        Args:
            workspace_dir: Directory for storing orchestration state and checkpoints
            checkpoint_interval: Interval for automatic checkpoints (iterations)
            execution_strategy: Strategy for executing workflow steps
            recovery_strategy: Strategy for handling failures and recovery
            resource_thresholds: Thresholds for resource monitoring
            monitoring_interval: Interval for resource monitoring (seconds)
        """
        self.workspace_dir = Path(workspace_dir)
        self.checkpoint_interval = checkpoint_interval
        self.execution_strategy = execution_strategy

        # Initialize directories
        self.workspace_dir.mkdir(exist_ok=True)
        self.checkpoint_dir = self.workspace_dir / "checkpoints"
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.state_dir = self.workspace_dir / "state"
        self.state_dir.mkdir(exist_ok=True)

        # Initialize managers
        self.checkpoint_manager = CheckpointManager(self.checkpoint_dir)
        self.recovery_manager = RecoveryManager(
            recovery_strategy or RecoveryStrategy(), self.checkpoint_manager
        )
        self.resource_monitor = ResourceMonitor(
            resource_thresholds or ResourceThresholds(), monitoring_interval
        )

        # Initialize state
        self.state = OrchestrationState.IDLE
        self.execution_context: Optional[ExecutionContext] = None
        self.workflow_steps: List[WorkflowStep] = []
        self.step_results: Dict[str, StepResult] = {}

        # Initialize components
        self.console = Console()

        # Register event handlers
        self._register_event_handlers()

        logger.info(f"WorkflowOrchestrator initialized with workspace: {self.workspace_dir}")

    def _register_event_handlers(self) -> None:
        """Register event handlers for orchestration events."""
        # Add resource monitoring alert callback
        self.resource_monitor.add_alert_callback(self._on_resource_alert)

    async def initialize_workflow(
        self,
        workflow_config: Dict[str, Any],
    ) -> bool:
        """Initialize a new workflow.

        Args:
            workflow_config: Configuration for the workflow

        Returns:
            True if initialization successful
        """
        try:
            self.state = OrchestrationState.INITIALIZING

            # Parse workflow configuration
            workflow_id = workflow_config.get("workflow_id", str(uuid.uuid4()))
            experiment_id = workflow_config.get("experiment_id")
            total_iterations = workflow_config.get("iterations", 1)

            # Create execution context
            self.execution_context = ExecutionContext(
                workflow_id=workflow_id,
                experiment_id=experiment_id,
                start_time=datetime.utcnow(),
                current_iteration=0,
                current_stage="initialization",
                total_iterations=total_iterations,
                state=OrchestrationState.INITIALIZING,
                checkpoint_interval=self.checkpoint_interval,
                last_checkpoint=None,
                resource_limits=workflow_config.get("resource_limits", {}),
                custom_context=workflow_config.get("custom_context", {}),
            )

            # Parse workflow steps
            self.workflow_steps = self._parse_workflow_steps(workflow_config.get("steps", []))

            # Validate workflow
            if not self._validate_workflow():
                raise ValueError("Workflow validation failed")

            # Start resource monitoring
            await self.resource_monitor.start_monitoring()

            # Publish initialization event
            await event_bus.publish(
                create_state_change_event(
                    old_state="idle",
                    new_state="initialized",
                    entity_type="workflow",
                    entity_id=workflow_id,
                )
            )

            self.state = OrchestrationState.IDLE
            logger.info(f"Workflow {workflow_id} initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize workflow: {e}")
            self.state = OrchestrationState.FAILED
            await event_bus.publish(
                create_error_event(
                    error_type="initialization_error",
                    error_message=str(e),
                    severity="critical",
                )
            )
            return False

    def _parse_workflow_steps(self, steps_config: List[Dict[str, Any]]) -> List[WorkflowStep]:
        """Parse workflow steps from configuration."""
        steps = []
        for step_config in steps_config:
            step = WorkflowStep(
                step_id=step_config.get("step_id", str(uuid.uuid4())),
                name=step_config["name"],
                component=step_config["component"],
                operation=step_config["operation"],
                dependencies=step_config.get("dependencies", []),
                parameters=step_config.get("parameters", {}),
                timeout=step_config.get("timeout"),
                retry_count=step_config.get("retry_count", 3),
                retry_delay=step_config.get("retry_delay", 1.0),
                critical=step_config.get("critical", True),
                parallel_group=step_config.get("parallel_group"),
                priority=step_config.get("priority", 0),
            )
            steps.append(step)
        return steps

    def _validate_workflow(self) -> bool:
        """Validate workflow configuration and dependencies."""
        if not self.workflow_steps:
            logger.error("No workflow steps defined")
            return False

        # Check for circular dependencies
        if self._has_circular_dependencies():
            logger.error("Circular dependencies detected in workflow")
            return False

        # Validate step references
        step_ids = {step.step_id for step in self.workflow_steps}
        for step in self.workflow_steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    logger.error(f"Invalid dependency '{dep}' in step '{step.step_id}'")
                    return False

        return True

    def _has_circular_dependencies(self) -> bool:
        """Check for circular dependencies in workflow steps."""
        # Build dependency graph
        graph = {}
        for step in self.workflow_steps:
            graph[step.step_id] = step.dependencies

        # DFS to detect cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            if node in rec_stack:
                return True
            if node in visited:
                return False

            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if has_cycle(neighbor):
                    return True

            rec_stack.remove(node)
            return False

        for step_id in graph:
            if step_id not in visited:
                if has_cycle(step_id):
                    return True

        return False

    async def execute_workflow(
        self,
        pipeline_instance: Any,
        resume_from_checkpoint: Optional[str] = None,
    ) -> WorkflowResult:
        """Execute the complete workflow with orchestration.

        Args:
            pipeline_instance: Instance of the evolution pipeline
            resume_from_checkpoint: Optional checkpoint ID to resume from

        Returns:
            Workflow execution results
        """
        if not self.execution_context:
            raise RuntimeError("Workflow not initialized")

        start_time = datetime.utcnow()

        try:
            # Handle resume from checkpoint
            if resume_from_checkpoint:
                await self._resume_from_checkpoint(resume_from_checkpoint)

            self.state = OrchestrationState.RUNNING
            self.execution_context.state = OrchestrationState.RUNNING

            # Execute workflow iterations
            iterations = await self._execute_workflow_iterations(pipeline_instance)

            # Create workflow result
            result = WorkflowResult(
                workflow_id=self.execution_context.workflow_id,
                experiment_id=self.execution_context.experiment_id,
                start_time=start_time,
                end_time=datetime.utcnow(),
                total_execution_time=(datetime.utcnow() - start_time).total_seconds(),
                iterations=iterations,
                success_count=sum(1 for it in iterations if it.success),
                failure_count=sum(1 for it in iterations if not it.success),
                checkpoints_created=len(self.checkpoint_manager.checkpoints),
                final_state=OrchestrationState.COMPLETED,
            )

            # Complete workflow
            await self._complete_workflow(result)

            return result

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")

            # Create failed workflow result
            result = WorkflowResult(
                workflow_id=self.execution_context.workflow_id,
                experiment_id=self.execution_context.experiment_id,
                start_time=start_time,
                end_time=datetime.utcnow(),
                total_execution_time=(datetime.utcnow() - start_time).total_seconds(),
                iterations=[],
                success_count=0,
                failure_count=1,
                checkpoints_created=len(self.checkpoint_manager.checkpoints),
                final_state=OrchestrationState.FAILED,
                error=str(e),
            )

            await self._handle_workflow_failure(e)
            return result

    async def _execute_workflow_iterations(
        self,
        pipeline_instance: Any,
    ) -> List[IterationResult]:
        """Execute workflow iterations with orchestration."""
        iterations = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:

            task = progress.add_task(
                "Executing workflow iterations...",
                total=self.execution_context.total_iterations,
            )

            for iteration in range(
                self.execution_context.current_iteration,
                self.execution_context.total_iterations,
            ):
                try:
                    self.execution_context.current_iteration = iteration

                    # Execute single iteration
                    iteration_result = await self._execute_single_iteration(
                        pipeline_instance, iteration
                    )

                    iterations.append(iteration_result)

                    # Check for checkpoint
                    if self._should_create_checkpoint(iteration):
                        await self._create_checkpoint(CheckpointType.AUTOMATIC)
                        logger.info(f"Created automatic checkpoint at iteration {iteration}")

                    # Update progress
                    progress.update(task, advance=1)

                    # Check for early termination conditions
                    if not iteration_result.should_continue:
                        logger.info("Early termination requested")
                        break

                except Exception as e:
                    logger.error(f"Iteration {iteration} failed: {e}")

                    # Create failed iteration result
                    failed_result = IterationResult(
                        iteration=iteration,
                        start_time=datetime.utcnow(),
                        end_time=datetime.utcnow(),
                        success=False,
                        execution_time=0.0,
                        stages={},
                        error=str(e),
                        should_continue=False,
                    )
                    iterations.append(failed_result)

                    # Attempt recovery
                    if await self.recovery_manager.attempt_recovery(
                        e, self.execution_context, iteration
                    ):
                        logger.info(f"Recovery successful for iteration {iteration}")
                        continue
                    else:
                        logger.error(f"Recovery failed for iteration {iteration}")
                        raise

        return iterations

    async def _execute_single_iteration(
        self,
        pipeline_instance: Any,
        iteration: int,
    ) -> IterationResult:
        """Execute a single workflow iteration."""
        iteration_start = datetime.utcnow()

        try:
            # Update context
            self.execution_context.current_stage = f"iteration_{iteration}"

            # Publish iteration start event
            await event_bus.publish(
                create_progress_event(
                    current=iteration,
                    total=self.execution_context.total_iterations,
                    stage=f"iteration_{iteration}",
                    message=f"Starting iteration {iteration}",
                )
            )

            # Execute workflow steps based on strategy
            if self.execution_strategy == ExecutionStrategy.SEQUENTIAL:
                stage_results = await self._execute_steps_sequential(pipeline_instance)
            elif self.execution_strategy == ExecutionStrategy.PARALLEL:
                stage_results = await self._execute_steps_parallel(pipeline_instance)
            else:
                # Default to sequential for adaptive and priority-based
                stage_results = await self._execute_steps_sequential(pipeline_instance)

            # Determine overall success
            success = all(result.success for result in stage_results.values())

            # Get current resource usage
            resource_usage = {}
            current_snapshot = self.resource_monitor.get_current_usage()
            if current_snapshot:
                resource_usage = {
                    "memory_percent": current_snapshot.memory_percent,
                    "cpu_percent": current_snapshot.cpu_percent,
                    "disk_percent": current_snapshot.disk_percent,
                }

            return IterationResult(
                iteration=iteration,
                start_time=iteration_start,
                end_time=datetime.utcnow(),
                success=success,
                execution_time=(datetime.utcnow() - iteration_start).total_seconds(),
                stages=stage_results,
                resource_usage=resource_usage,
                should_continue=success,  # Continue if successful
            )

        except Exception as e:
            logger.error(f"Iteration {iteration} execution failed: {e}")
            return IterationResult(
                iteration=iteration,
                start_time=iteration_start,
                end_time=datetime.utcnow(),
                success=False,
                execution_time=(datetime.utcnow() - iteration_start).total_seconds(),
                stages={},
                error=str(e),
                should_continue=False,
            )

    async def _execute_steps_sequential(
        self,
        pipeline_instance: Any,
    ) -> Dict[str, StepResult]:
        """Execute workflow steps sequentially."""
        results = {}

        # Sort steps by dependencies
        sorted_steps = self._topological_sort_steps()

        for step in sorted_steps:
            step_result = await self._execute_single_step(pipeline_instance, step)
            results[step.step_id] = step_result

            # Store in instance results
            self.step_results[step.step_id] = step_result

            # Stop on critical step failure
            if not step_result.success and step.critical:
                logger.error(f"Critical step {step.step_id} failed, stopping execution")
                break

        return results

    async def _execute_steps_parallel(
        self,
        pipeline_instance: Any,
    ) -> Dict[str, StepResult]:
        """Execute workflow steps in parallel where possible."""
        results = {}
        executed_steps = set()

        while len(executed_steps) < len(self.workflow_steps):
            # Find steps ready for execution
            ready_steps = []
            for step in self.workflow_steps:
                if step.step_id not in executed_steps and all(
                    dep in executed_steps for dep in step.dependencies
                ):
                    ready_steps.append(step)

            if not ready_steps:
                logger.error("No ready steps found - possible deadlock")
                break

            # Execute ready steps in parallel
            tasks = [self._execute_single_step(pipeline_instance, step) for step in ready_steps]

            step_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for step, result in zip(ready_steps, step_results):
                if isinstance(result, Exception):
                    logger.error(f"Step {step.step_id} execution failed: {result}")
                    step_result = StepResult(
                        step_id=step.step_id,
                        name=step.name,
                        success=False,
                        execution_time=0.0,
                        retry_count=0,
                        error=str(result),
                    )
                else:
                    step_result = result

                results[step.step_id] = step_result
                self.step_results[step.step_id] = step_result
                executed_steps.add(step.step_id)

        return results

    async def _execute_single_step(
        self,
        pipeline_instance: Any,
        step: WorkflowStep,
    ) -> StepResult:
        """Execute a single workflow step with retry logic."""
        step_start = datetime.utcnow()

        for attempt in range(step.retry_count + 1):
            try:
                execution_start = time.time()

                # Update context
                self.execution_context.current_stage = step.name

                # Publish step start event
                await publish_pipeline_stage_event(
                    stage=step.name,
                    status="started",
                    iteration=self.execution_context.current_iteration,
                )

                # Execute step with timeout
                if step.timeout:
                    result = await asyncio.wait_for(
                        self._call_component_method(
                            pipeline_instance, step.component, step.operation, step.parameters
                        ),
                        timeout=step.timeout,
                    )
                else:
                    result = await self._call_component_method(
                        pipeline_instance, step.component, step.operation, step.parameters
                    )

                execution_time = time.time() - execution_start

                # Publish step completion event
                await publish_pipeline_stage_event(
                    stage=step.name,
                    status="completed",
                    iteration=self.execution_context.current_iteration,
                    data={"execution_time": execution_time},
                )

                return StepResult(
                    step_id=step.step_id,
                    name=step.name,
                    success=True,
                    execution_time=execution_time,
                    retry_count=attempt,
                    result=result,
                    start_time=step_start,
                    end_time=datetime.utcnow(),
                )

            except Exception as e:
                execution_time = time.time() - execution_start

                if attempt < step.retry_count:
                    logger.warning(
                        f"Step {step.step_id} attempt {attempt + 1} failed, retrying: {e}"
                    )
                    await asyncio.sleep(step.retry_delay * (2**attempt))
                else:
                    logger.error(f"Step {step.step_id} failed after {attempt + 1} attempts: {e}")

                    # Publish step failure event
                    await publish_pipeline_stage_event(
                        stage=step.name,
                        status="failed",
                        iteration=self.execution_context.current_iteration,
                        error=str(e),
                    )

                    return StepResult(
                        step_id=step.step_id,
                        name=step.name,
                        success=False,
                        execution_time=execution_time,
                        retry_count=attempt,
                        error=str(e),
                        start_time=step_start,
                        end_time=datetime.utcnow(),
                    )

    async def _call_component_method(
        self,
        pipeline_instance: Any,
        component: str,
        operation: str,
        parameters: Dict[str, Any],
    ) -> Any:
        """Call a method on a pipeline component."""
        # Get component from pipeline
        if hasattr(pipeline_instance, component):
            component_obj = getattr(pipeline_instance, component)
        else:
            raise AttributeError(f"Component {component} not found")

        # Get method
        if hasattr(component_obj, operation):
            method = getattr(component_obj, operation)
        else:
            raise AttributeError(f"Operation {operation} not found on component {component}")

        # Call method
        if asyncio.iscoroutinefunction(method):
            return await method(**parameters)
        else:
            return method(**parameters)

    def _topological_sort_steps(self) -> List[WorkflowStep]:
        """Sort workflow steps topologically based on dependencies."""
        # Kahn's algorithm
        in_degree = {step.step_id: 0 for step in self.workflow_steps}
        graph = {step.step_id: [] for step in self.workflow_steps}
        step_map = {step.step_id: step for step in self.workflow_steps}

        # Build graph and calculate in-degrees
        for step in self.workflow_steps:
            for dep in step.dependencies:
                graph[dep].append(step.step_id)
                in_degree[step.step_id] += 1

        # Find nodes with no incoming edges
        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(step_map[current])

            # Remove edges
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def _should_create_checkpoint(self, iteration: int) -> bool:
        """Determine if a checkpoint should be created."""
        if iteration == 0:
            return False

        # Automatic checkpoint interval
        if iteration % self.checkpoint_interval == 0:
            return True

        return False

    async def _create_checkpoint(self, checkpoint_type: CheckpointType) -> str:
        """Create a workflow checkpoint."""
        if not self.execution_context:
            raise RuntimeError("No execution context available")

        # Get current resource usage
        resource_usage = {}
        current_snapshot = self.resource_monitor.get_current_usage()
        if current_snapshot:
            resource_usage = {
                "memory_percent": current_snapshot.memory_percent,
                "cpu_percent": current_snapshot.cpu_percent,
                "disk_percent": current_snapshot.disk_percent,
            }

        return await self.checkpoint_manager.create_checkpoint(
            checkpoint_type=checkpoint_type,
            execution_context=self.execution_context,
            workflow_steps=self.workflow_steps,
            step_results=self.step_results,
            state=self.state,
            resource_usage=resource_usage,
        )

    async def _resume_from_checkpoint(self, checkpoint_id: str) -> None:
        """Resume workflow execution from a checkpoint."""
        checkpoint_data = self.checkpoint_manager.get_checkpoint(checkpoint_id)

        if not checkpoint_data:
            raise FileNotFoundError(f"Checkpoint {checkpoint_id} not found")

        # Restore execution context
        context_data = checkpoint_data["execution_context"]
        self.execution_context = ExecutionContext(
            workflow_id=context_data["workflow_id"],
            experiment_id=context_data["experiment_id"],
            start_time=datetime.fromisoformat(context_data["start_time"]),
            current_iteration=context_data["current_iteration"],
            current_stage=context_data["current_stage"],
            total_iterations=context_data["total_iterations"],
            state=OrchestrationState(context_data["state"]),
            checkpoint_interval=context_data["checkpoint_interval"],
            last_checkpoint=(
                datetime.fromisoformat(context_data["last_checkpoint"])
                if context_data["last_checkpoint"]
                else None
            ),
            resource_limits=context_data["resource_limits"],
            custom_context=context_data["custom_context"],
        )

        # Restore workflow steps
        steps_data = checkpoint_data["workflow_steps"]
        self.workflow_steps = [WorkflowStep(**step_data) for step_data in steps_data]

        # Restore step results
        step_results_data = checkpoint_data["step_results"]
        self.step_results = {}
        for step_id, result_data in step_results_data.items():
            if isinstance(result_data, dict):
                self.step_results[step_id] = StepResult(**result_data)

        # Restore state
        self.state = OrchestrationState(checkpoint_data["state"])

        logger.info(f"Resumed from checkpoint: {checkpoint_id}")

    async def _complete_workflow(self, result: WorkflowResult) -> None:
        """Complete the workflow execution."""
        self.state = OrchestrationState.COMPLETED

        # Create final checkpoint
        await self._create_checkpoint(CheckpointType.MILESTONE)

        # Stop resource monitoring
        await self.resource_monitor.stop_monitoring()

        logger.info("Workflow execution completed successfully")

    async def _handle_workflow_failure(self, error: Exception) -> None:
        """Handle workflow failure."""
        self.state = OrchestrationState.FAILED

        # Create error checkpoint
        await self._create_checkpoint(CheckpointType.ERROR_RECOVERY)

        # Stop resource monitoring
        await self.resource_monitor.stop_monitoring()

        logger.error(f"Workflow execution failed: {error}")

    async def _on_resource_alert(self, alert) -> None:
        """Handle resource alerts."""
        logger.warning(f"Resource alert: {alert.severity} - {alert.message}")

        # Create checkpoint on critical alerts
        if alert.severity == "critical" and self.execution_context:
            try:
                await self._create_checkpoint(CheckpointType.AUTOMATIC)
                logger.info("Created emergency checkpoint due to resource alert")
            except Exception as e:
                logger.error(f"Failed to create emergency checkpoint: {e}")

    # Public API methods
    async def pause_workflow(self) -> bool:
        """Pause the current workflow execution."""
        if self.state == OrchestrationState.RUNNING:
            self.state = OrchestrationState.PAUSED
            await self._create_checkpoint(CheckpointType.MANUAL)
            logger.info("Workflow paused")
            return True
        return False

    async def resume_workflow(self) -> bool:
        """Resume a paused workflow execution."""
        if self.state == OrchestrationState.PAUSED:
            self.state = OrchestrationState.RUNNING
            logger.info("Workflow resumed")
            return True
        return False

    async def cancel_workflow(self) -> bool:
        """Cancel the current workflow execution."""
        if self.state in [OrchestrationState.RUNNING, OrchestrationState.PAUSED]:
            self.state = OrchestrationState.CANCELLED
            await self.resource_monitor.stop_monitoring()
            logger.info("Workflow cancelled")
            return True
        return False

    def get_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status."""
        status = {
            "state": self.state.value,
            "execution_context": None,
            "resource_usage": None,
            "active_alerts": [],
            "checkpoint_count": len(self.checkpoint_manager.checkpoints),
            "recovery_attempts": len(self.recovery_manager.recovery_attempts),
        }

        if self.execution_context:
            status["execution_context"] = {
                "workflow_id": self.execution_context.workflow_id,
                "current_iteration": self.execution_context.current_iteration,
                "total_iterations": self.execution_context.total_iterations,
                "current_stage": self.execution_context.current_stage,
            }

        # Get current resource usage
        current_snapshot = self.resource_monitor.get_current_usage()
        if current_snapshot:
            status["resource_usage"] = {
                "memory_percent": current_snapshot.memory_percent,
                "cpu_percent": current_snapshot.cpu_percent,
                "disk_percent": current_snapshot.disk_percent,
            }

        # Get active alerts
        status["active_alerts"] = [
            {
                "resource_type": alert.resource_type,
                "severity": alert.severity,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
            }
            for alert in self.resource_monitor.get_active_alerts()
        ]

        return status
