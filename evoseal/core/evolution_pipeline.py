"""
Evolution Pipeline Module

This module implements the core EvolutionPipeline class that orchestrates the entire
evolution process by integrating DGM, OpenEvolve, and SEAL components.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from rich.console import Console

from evoseal.core.controller import Controller as EvolutionController
from evoseal.core.improvement_validator import ImprovementValidator
from evoseal.core.metrics_tracker import MetricsTracker
from evoseal.core.testrunner import TestRunner
from evoseal.core.version_database import VersionDatabase
from evoseal.core.workflow import WorkflowEngine

from .events import (
    Event,
    EventBus,
    EventType,
    create_error_event,
    create_progress_event,
    create_state_change_event,
    event_bus,
    publish_component_lifecycle_event,
    publish_pipeline_stage_event,
)
from .repository import RepositoryManager

# Type aliases
VersionID = Union[int, str]

# Logger
logger = logging.getLogger(__name__)


@dataclass
class EvolutionConfig:
    """Configuration for the EvolutionPipeline."""

    # DGM Configuration
    dgm_config: Dict[str, Any] = field(default_factory=dict)

    # OpenEvolve Configuration
    openevolve_config: Dict[str, Any] = field(default_factory=dict)

    # SEAL Configuration
    seal_config: Dict[str, Any] = field(default_factory=dict)

    # Testing Configuration
    test_config: Dict[str, Any] = field(default_factory=dict)

    # Metrics Configuration
    metrics_config: Dict[str, Any] = field(default_factory=dict)

    # Validation Configuration
    validation_config: Dict[str, Any] = field(default_factory=dict)

    # Version Control Configuration
    version_control_config: Dict[str, Any] = field(default_factory=dict)


class EvolutionPipeline:
    """
    Core orchestrator for the evolution process.

    This class integrates DGM, OpenEvolve, and SEAL components to manage
    the complete code evolution workflow.
    """

    def __init__(self, config: Optional[Union[Dict[str, Any], EvolutionConfig]] = None):
        """Initialize the EvolutionPipeline.

        Args:
            config: Configuration dictionary or EvolutionConfig instance.
                   If None, uses default configuration.
        """
        # Initialize configuration
        if config is None:
            self.config = EvolutionConfig()
        elif isinstance(config, dict):
            self.config = EvolutionConfig(**config)
        else:
            self.config = config

        # Initialize components
        self.event_bus = EventBus()
        self.console = Console()

        # Initialize core components
        self.version_db = VersionDatabase()
        self.metrics_tracker = MetricsTracker(self.config.metrics_config)
        self.test_runner = TestRunner(self.config.test_config)
        self.validator = ImprovementValidator(self.config.validation_config, self.metrics_tracker)

        # Initialize workflow engine
        self.workflow_engine = WorkflowEngine()

        # Initialize component connectors
        self._init_component_connectors()

        # Register event handlers
        self._register_event_handlers()

        logger.info("EvolutionPipeline initialized")

    def _init_component_connectors(self) -> None:
        """Initialize connectors to external components."""
        from ..integration.base_adapter import ComponentType
        from ..integration.orchestrator import IntegrationOrchestrator

        # Initialize the integration orchestrator
        self.integration_orchestrator = IntegrationOrchestrator()

        # Initialize component configurations from pipeline config
        component_configs = {}

        # DGM configuration
        if hasattr(self.config, 'dgm_config') and self.config.dgm_config:
            component_configs[ComponentType.DGM] = self.config.dgm_config

        # OpenEvolve configuration
        if hasattr(self.config, 'openevolve_config') and self.config.openevolve_config:
            component_configs[ComponentType.OPENEVOLVE] = self.config.openevolve_config

        # SEAL configuration
        if hasattr(self.config, 'seal_config') and self.config.seal_config:
            component_configs[ComponentType.SEAL] = self.config.seal_config

        # Store component configs for async initialization
        self._component_configs = component_configs

        # Legacy connectors for backward compatibility
        self.dgm_connector = None
        self.openevolve_connector = None
        self.seal_connector = None

    def _register_event_handlers(self) -> None:
        """Register event handlers for the pipeline."""
        self.event_bus.subscribe(EventType.WORKFLOW_STARTED, self._on_workflow_started)
        self.event_bus.subscribe(EventType.WORKFLOW_COMPLETED, self._on_workflow_completed)
        self.event_bus.subscribe(EventType.STEP_STARTED, self._on_step_started)
        self.event_bus.subscribe(EventType.STEP_COMPLETED, self._on_step_completed)

    async def run_evolution_cycle(self, iterations: int = 1) -> List[Dict[str, Any]]:
        """Run a complete evolution cycle.

        Args:
            iterations: Number of evolution iterations to run.

        Returns:
            List of results from each iteration.
        """
        results = []

        try:
            # Publish evolution started event
            await event_bus.publish(
                Event(
                    event_type=EventType.EVOLUTION_STARTED,
                    source="evolution_pipeline",
                    data={
                        "timestamp": datetime.utcnow().isoformat(),
                        "total_iterations": iterations,
                        "pipeline_id": id(self),
                    },
                )
            )

            for i in range(iterations):
                # Publish iteration started event
                await event_bus.publish(
                    create_progress_event(
                        current=i,
                        total=iterations,
                        stage="evolution_iteration",
                        source="evolution_pipeline",
                        message=f"Starting iteration {i + 1} of {iterations}",
                        event_type=EventType.ITERATION_STARTED,
                        iteration=i + 1,
                    )
                )

                try:
                    iteration_result = await self._run_single_iteration(i + 1)
                    results.append(iteration_result)

                    # Publish iteration completed event
                    await event_bus.publish(
                        create_progress_event(
                            current=i + 1,
                            total=iterations,
                            stage="evolution_iteration",
                            source="evolution_pipeline",
                            message=f"Completed iteration {i + 1} of {iterations}",
                            event_type=EventType.ITERATION_COMPLETED,
                            iteration=i + 1,
                            result=iteration_result,
                        )
                    )
                except Exception as iteration_error:
                    # Publish iteration failed event
                    await event_bus.publish(
                        create_error_event(
                            error=iteration_error,
                            source="evolution_pipeline",
                            event_type=EventType.ITERATION_FAILED,
                            iteration=i + 1,
                            total_iterations=iterations,
                        )
                    )
                    raise

                # Check if we should continue evolving
                if not iteration_result["should_continue"]:
                    break

            self.event_bus.publish(
                Event(
                    EventType.EVOLUTION_COMPLETED,
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "iterations_completed": len(results),
                        "successful_iterations": sum(1 for r in results if r["success"]),
                    },
                )
            )

        except Exception as e:
            logger.exception("Error during evolution cycle")
            self.event_bus.publish(
                Event(
                    EventType.ERROR_OCCURRED,
                    {"error": str(e), "timestamp": datetime.utcnow().isoformat()},
                )
            )
            raise

        return results

    async def _run_single_iteration(self, iteration: int) -> Dict[str, Any]:
        """Run a single evolution iteration."""
        iteration_result = {
            "iteration": iteration,
            "success": False,
            "metrics": {},
            "should_continue": True,
        }

        try:
            # 1. Analyze current version
            await publish_pipeline_stage_event(
                stage="analyzing",
                status="started",
                source="evolution_pipeline",
                iteration=iteration,
            )
            analysis = await self._analyze_current_version()
            await publish_pipeline_stage_event(
                stage="analyzing",
                status="completed",
                source="evolution_pipeline",
                iteration=iteration,
                analysis_result=analysis,
            )

            # 2. Generate improvements
            await publish_pipeline_stage_event(
                stage="generating",
                status="started",
                source="evolution_pipeline",
                iteration=iteration,
            )
            improvements = await self._generate_improvements(analysis)
            await publish_pipeline_stage_event(
                stage="generating",
                status="completed",
                source="evolution_pipeline",
                iteration=iteration,
                improvements_count=len(improvements) if improvements else 0,
            )

            # 3. Apply SEAL adaptations
            await publish_pipeline_stage_event(
                stage="adapting", status="started", source="evolution_pipeline", iteration=iteration
            )
            adapted_improvements = await self._adapt_improvements(improvements)
            await publish_pipeline_stage_event(
                stage="adapting",
                status="completed",
                source="evolution_pipeline",
                iteration=iteration,
                adapted_count=len(adapted_improvements) if adapted_improvements else 0,
            )

            # 4. Create and evaluate new version
            await publish_pipeline_stage_event(
                stage="evaluating",
                status="started",
                source="evolution_pipeline",
                iteration=iteration,
            )
            evaluation_result = await self._evaluate_version(adapted_improvements)
            await publish_pipeline_stage_event(
                stage="evaluating",
                status="completed",
                source="evolution_pipeline",
                iteration=iteration,
                evaluation_score=evaluation_result.get("score", 0),
            )

            # 5. Validate improvement
            await publish_pipeline_stage_event(
                stage="validating",
                status="started",
                source="evolution_pipeline",
                iteration=iteration,
            )
            is_improvement = await self._validate_improvement(evaluation_result)

            # Update iteration result
            iteration_result.update(
                {
                    "success": True,
                    "is_improvement": is_improvement,
                    "metrics": evaluation_result.get("metrics", {}),
                    "should_continue": is_improvement,  # Continue if we found an improvement
                }
            )

        except Exception as e:
            logger.error(f"Error in iteration {iteration}: {str(e)}")
            iteration_result["error"] = str(e)

        return iteration_result

    async def _analyze_current_version(self) -> Dict[str, Any]:
        """Analyze the current version of the code."""
        # TODO: Implement analysis logic
        return {}

    async def _generate_improvements(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate potential improvements based on analysis."""
        # TODO: Implement improvement generation logic
        return []

    async def _adapt_improvements(self, improvements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adapt improvements using SEAL."""
        # TODO: Implement SEAL adaptation logic
        return improvements

    async def _evaluate_version(self, improvements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate a new version with the given improvements."""
        # TODO: Implement version evaluation logic
        return {"metrics": {}}

    async def _validate_improvement(self, evaluation_result: Dict[str, Any]) -> bool:
        """Validate if the new version is an improvement."""
        # TODO: Implement improvement validation logic
        return True

    # Integration orchestrator methods

    async def initialize_components(self) -> bool:
        """Initialize all component adapters."""
        if not hasattr(self, 'integration_orchestrator'):
            logger.error("Integration orchestrator not initialized")
            return False

        try:
            # Publish component initialization started event
            await event_bus.publish(
                Event(
                    event_type=EventType.COMPONENT_INITIALIZING,
                    source="evolution_pipeline",
                    data={"pipeline_id": id(self), "timestamp": datetime.utcnow().isoformat()},
                )
            )

            success = await self.integration_orchestrator.initialize(self._component_configs)

            if success:
                logger.info("All components initialized successfully")
                # Update legacy connectors for backward compatibility
                self._update_legacy_connectors()

                # Publish successful initialization event
                await event_bus.publish(
                    Event(
                        event_type=EventType.COMPONENT_READY,
                        source="evolution_pipeline",
                        data={
                            "pipeline_id": id(self),
                            "timestamp": datetime.utcnow().isoformat(),
                            "components_initialized": True,
                        },
                    )
                )
            else:
                logger.error("Failed to initialize some components")
                # Publish initialization failed event
                await event_bus.publish(
                    create_error_event(
                        error="Failed to initialize some components",
                        source="evolution_pipeline",
                        event_type=EventType.COMPONENT_FAILED,
                        pipeline_id=id(self),
                    )
                )
            return success
        except Exception as e:
            logger.exception("Error initializing components")
            # Publish initialization error event
            await event_bus.publish(
                create_error_event(
                    error=e,
                    source="evolution_pipeline",
                    event_type=EventType.COMPONENT_FAILED,
                    pipeline_id=id(self),
                    operation="initialize",
                )
            )
            return False

    async def start_components(self) -> bool:
        """Start all component adapters."""
        if not hasattr(self, 'integration_orchestrator'):
            logger.error("Integration orchestrator not initialized")
            return False

        try:
            # Publish components starting event
            await event_bus.publish(
                Event(
                    event_type=EventType.COMPONENT_STARTING,
                    source="evolution_pipeline",
                    data={"pipeline_id": id(self), "timestamp": datetime.utcnow().isoformat()},
                )
            )

            success = await self.integration_orchestrator.start()

            if success:
                # Publish components started event
                await event_bus.publish(
                    Event(
                        event_type=EventType.COMPONENT_STARTED,
                        source="evolution_pipeline",
                        data={
                            "pipeline_id": id(self),
                            "timestamp": datetime.utcnow().isoformat(),
                            "all_components_started": True,
                        },
                    )
                )
            else:
                # Publish start failed event
                await event_bus.publish(
                    create_error_event(
                        error="Failed to start some components",
                        source="evolution_pipeline",
                        event_type=EventType.COMPONENT_FAILED,
                        pipeline_id=id(self),
                        operation="start",
                    )
                )

            return success
        except Exception as e:
            logger.exception("Error starting components")
            # Publish start error event
            await event_bus.publish(
                create_error_event(
                    error=e,
                    source="evolution_pipeline",
                    event_type=EventType.COMPONENT_FAILED,
                    pipeline_id=id(self),
                    operation="start",
                )
            )
            return False

    async def stop_components(self) -> bool:
        """Stop all component adapters."""
        if not hasattr(self, 'integration_orchestrator'):
            return True

        try:
            # Publish components stopping event
            await event_bus.publish(
                Event(
                    event_type=EventType.COMPONENT_STOPPING,
                    source="evolution_pipeline",
                    data={"pipeline_id": id(self), "timestamp": datetime.utcnow().isoformat()},
                )
            )

            success = await self.integration_orchestrator.stop()

            if success:
                # Publish components stopped event
                await event_bus.publish(
                    Event(
                        event_type=EventType.COMPONENT_STOPPED,
                        source="evolution_pipeline",
                        data={
                            "pipeline_id": id(self),
                            "timestamp": datetime.utcnow().isoformat(),
                            "all_components_stopped": True,
                        },
                    )
                )
            else:
                # Publish stop failed event
                await event_bus.publish(
                    create_error_event(
                        error="Failed to stop some components",
                        source="evolution_pipeline",
                        event_type=EventType.COMPONENT_FAILED,
                        pipeline_id=id(self),
                        operation="stop",
                    )
                )

            return success
        except Exception as e:
            logger.exception("Error stopping components")
            # Publish stop error event
            await event_bus.publish(
                create_error_event(
                    error=e,
                    source="evolution_pipeline",
                    event_type=EventType.COMPONENT_FAILED,
                    pipeline_id=id(self),
                    operation="stop",
                )
            )
            return False

    def get_component_status(self) -> Dict[str, Any]:
        """Get status of all components."""
        if not hasattr(self, 'integration_orchestrator'):
            return {"error": "Integration orchestrator not initialized"}

        try:
            status = self.integration_orchestrator.get_all_status()
            return {
                component_type.value: {
                    "state": component_status.state.value,
                    "message": component_status.message,
                    "last_updated": component_status.last_updated,
                    "error": component_status.error,
                }
                for component_type, component_status in status.items()
            }
        except Exception as e:
            logger.exception("Error getting component status")
            return {"error": str(e)}

    async def get_component_metrics(self) -> Dict[str, Any]:
        """Get metrics from all components."""
        if not hasattr(self, 'integration_orchestrator'):
            return {"error": "Integration orchestrator not initialized"}

        try:
            return await self.integration_orchestrator.get_all_metrics()
        except Exception as e:
            logger.exception("Error getting component metrics")
            return {"error": str(e)}

    async def execute_evolution_workflow(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a complete evolution workflow using all components."""
        if not hasattr(self, 'integration_orchestrator'):
            return {"error": "Integration orchestrator not initialized", "success": False}

        try:
            return await self.integration_orchestrator.execute_evolution_workflow(workflow_config)
        except Exception as e:
            logger.exception("Error executing evolution workflow")
            return {"error": str(e), "success": False}

    def _update_legacy_connectors(self) -> None:
        """Update legacy connectors for backward compatibility."""
        from ..integration.base_adapter import ComponentType

        if hasattr(self, 'integration_orchestrator'):
            self.dgm_connector = self.integration_orchestrator.get_component(ComponentType.DGM)
            self.openevolve_connector = self.integration_orchestrator.get_component(
                ComponentType.OPENEVOLVE
            )
            self.seal_connector = self.integration_orchestrator.get_component(ComponentType.SEAL)

    # Event Handlers
    def _on_workflow_started(self, event: Event) -> None:
        """Handle workflow started event."""
        logger.info(f"Workflow started: {event.data}")

    def _on_workflow_completed(self, event: Event) -> None:
        """Handle workflow completed event."""
        logger.info(f"Workflow completed: {event.data}")

    def _on_step_started(self, event: Event) -> None:
        """Handle step started event."""
        logger.debug(f"Step started: {event.data}")

    def _on_step_completed(self, event: Event) -> None:
        """Handle step completed event."""
        logger.debug(f"Step completed: {event.data}")


class WorkflowState(str, Enum):
    """Represents the state of a workflow."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStage(Enum):
    """Represents the stages of the evolution workflow."""

    INITIALIZING = "initializing"
    ANALYZING = "analyzing"
    GENERATING = "generating_improvements"
    ADAPTING = "adapting_improvements"
    EVALUATING = "evaluating_version"
    VALIDATING = "validating_improvement"
    FINALIZING = "finalizing"

    @classmethod
    def get_stage_order(cls) -> List['WorkflowStage']:
        """Get the ordered list of workflow stages."""
        return [
            cls.INITIALIZING,
            cls.ANALYZING,
            cls.GENERATING,
            cls.ADAPTING,
            cls.EVALUATING,
            cls.VALIDATING,
            cls.FINALIZING,
        ]

    @classmethod
    def get_required_stages(cls, stage: 'WorkflowStage') -> List['WorkflowStage']:
        """Get the list of stages that must be completed before the given stage."""
        stage_order = cls.get_stage_order()
        try:
            stage_index = stage_order.index(stage)
            return stage_order[:stage_index]
        except ValueError:
            return []

    @classmethod
    def validate_stage_transition(
        cls, from_stage: Optional['WorkflowStage'], to_stage: 'WorkflowStage'
    ) -> bool:
        """Validate if a transition between stages is allowed."""
        if from_stage is None:
            return to_stage == cls.INITIALIZING

        stage_order = cls.get_stage_order()
        try:
            from_idx = stage_order.index(from_stage)
            to_idx = stage_order.index(to_stage)
            return from_idx <= to_idx <= from_idx + 1
        except ValueError:
            return False

    """Coordinates the execution of evolution workflows.

    This class provides a higher-level interface for running evolution workflows
    with support for pausing, resuming, and error recovery.

    Example usage:
    ```python
    # Initialize the coordinator
    coordinator = WorkflowCoordinator("path/to/config.json")

    # Run the workflow
    results = await coordinator.run_workflow(
        "https://github.com/example/repo.git",
        iterations=5
    )

    # Pause the workflow (can be called from another thread)
    coordinator.request_pause()

    # Resume the workflow
    coordinator.resume()

    # Get current status
    status = coordinator.get_status()
    print(f"Current stage: {status['current_stage']}")
    ```

    The workflow consists of the following stages:
    1. INITIALIZING: Set up the repository and environment
    2. ANALYZING: Analyze the current codebase
    3. GENERATING: Generate potential improvements
    4. ADAPTING: Adapt improvements to the codebase
    5. EVALUATING: Evaluate the adapted code
    6. VALIDATING: Validate if the changes are improvements
    7. FINALIZING: Clean up and finalize the workflow
    """

    # Class-level constants
    STATE_FILE = "workflow_state.json"
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    MAX_STAGE_ATTEMPTS = 3

    def __init__(self, config_path: str, work_dir: Optional[str] = None):
        """Initialize the WorkflowCoordinator.

        Args:
            config_path: Path to the configuration file.
            work_dir: Working directory for storing state and temporary files.
                     If None, uses a temporary directory.
        """
        self.config_path = Path(config_path).resolve()
        self.work_dir = Path(work_dir) if work_dir else Path.cwd() / "work"
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Initialize state
        self.state = WorkflowState.NOT_STARTED
        self.current_stage = None
        self.stage_results = {}
        self.retry_count = 0
        self.current_repo = None
        self.current_branch = None
        self.pause_requested = False
        self.stage_attempts = 0
        self.last_error = None

        # Initialize repository manager
        self.repo_manager = RepositoryManager(self.work_dir)

        # Load configuration and initialize pipeline
        self.config = self._load_config()
        self.pipeline = EvolutionPipeline(self.config)

        # Load saved state if it exists
        self._load_state()

        # Initialize stage callbacks
        self._init_stage_callbacks()

    def _init_stage_callbacks(self) -> None:
        """Initialize callbacks for each workflow stage."""
        self.stage_callbacks = {
            WorkflowStage.INITIALIZING: self._initialize_repository,
            WorkflowStage.ANALYZING: self._analyze_code,
            WorkflowStage.GENERATING: self._generate_improvements,
            WorkflowStage.ADAPTING: self._adapt_improvements,
            WorkflowStage.EVALUATING: self._evaluate_changes,
            WorkflowStage.VALIDATING: self._validate_improvement,
            WorkflowStage.FINALIZING: self._finalize_workflow,
        }

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def _get_state_file(self) -> Path:
        """Get the path to the state file."""
        return self.work_dir / self.STATE_FILE

    def _save_state(self) -> None:
        """Save the current workflow state to disk."""
        state = {
            "state": self.state.value,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "stage_results": self.stage_results,
            "retry_count": self.retry_count,
            "config_path": str(self.config_path),
            "work_dir": str(self.work_dir),
        }

        with open(self._get_state_file(), 'w') as f:
            json.dump(state, f, indent=2)

    def _load_state(self) -> bool:
        """Load workflow state from disk.

        Returns:
            bool: True if state was loaded successfully, False otherwise
        """
        state_file = self._get_state_file()
        if not state_file.exists():
            return False

        try:
            with open(state_file, 'r') as f:
                state = json.load(f)

            self.state = WorkflowState(state["state"])
            self.current_stage = (
                WorkflowStage(state["current_stage"]) if state["current_stage"] else None
            )
            self.stage_results = state["stage_results"]
            self.retry_count = state["retry_count"]

            return True
        except Exception as e:
            logger.warning(f"Failed to load workflow state: {e}")
            return False

    def _clear_state(self) -> None:
        """Clear the saved workflow state."""
        state_file = self._get_state_file()
        if state_file.exists():
            state_file.unlink()

    async def _execute_stage(self, stage: WorkflowStage, func, *args, **kwargs):
        """Execute a workflow stage with retry logic and repository state management.

        This method:
        1. Validates the stage transition
        2. Sets up the repository state for the stage
        3. Executes the stage function with retry logic
        4. Handles repository operations like committing changes
        5. Manages workflow state persistence
        6. Handles pause/resume functionality

        Args:
            stage: The current workflow stage
            func: The function to execute
            *args, **kwargs: Arguments to pass to the function

        Returns:
            The result of the function call

        Raises:
            Exception: If max retries are exceeded or a critical error occurs
        """
        # Validate stage transition
        if not WorkflowStage.validate_stage_transition(self.current_stage, stage):
            raise ValueError(f"Invalid stage transition from {self.current_stage} to {stage}")

        self.current_stage = stage
        self.stage_attempts = 0
        self.last_error = None

        # Setup repository state for this stage
        if self.current_repo:
            self._prepare_repository_for_stage(stage)

        while self.stage_attempts < self.MAX_STAGE_ATTEMPTS:
            try:
                # Check for pause request
                if self.pause_requested:
                    self.pause()
                    self.pause_requested = False
                    return None

                # Check if we're in a paused state
                if self.state == WorkflowState.PAUSED:
                    logger.info("Workflow is paused, waiting to resume...")
                    await asyncio.sleep(5)  # Check every 5 seconds
                    continue

                # Update state and log
                self.state = WorkflowState.RUNNING
                logger.info(
                    f"Starting stage: {stage.value} (attempt {self.stage_attempts + 1}/{self.MAX_STAGE_ATTEMPTS})"
                )

                # Execute the stage function
                result = await self._execute_stage_function(stage, func, *args, **kwargs)

                # Handle successful stage completion
                self._handle_stage_success(stage, result)
                return result

            except ConflictError as ce:
                # Handle merge conflicts specifically
                self.last_error = ce
                if not self._handle_conflict(stage, ce):
                    self.state = WorkflowState.FAILED
                    self._save_state()
                    raise

            except Exception as e:
                self.last_error = e
                if not self._handle_error(e, stage):
                    self.state = WorkflowState.FAILED
                    self._save_state()
                    raise

            # Increment attempt counter
            self.stage_attempts += 1

            # If we've exhausted all attempts, handle the failure
            if self.stage_attempts >= self.MAX_STAGE_ATTEMPTS:
                self._handle_stage_failure(stage)

    async def _execute_stage_function(self, stage: WorkflowStage, func, *args, **kwargs):
        """Execute a single attempt of a stage function with proper error handling."""
        try:
            # Execute the function (supports both sync and async functions)
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # If we got here, the stage completed successfully
            return result

        except Exception as e:
            logger.error(f"Error in stage {stage.value}: {e}", exc_info=True)
            raise

    def _handle_error(self, error: Exception, stage: WorkflowStage) -> bool:
        """Handle errors during workflow execution.

        Args:
            error: The exception that occurred
            stage: The current workflow stage

        Returns:
            bool: True if the error was handled and execution can continue,
                  False if the workflow should stop
        """
        logger.error(
            f"Error in stage {stage.value} (attempt {self.stage_attempts + 1}/"
            f"{self.MAX_STAGE_ATTEMPTS}): {error}",
            exc_info=True,
        )

        # Handle specific error types
        if isinstance(error, GitCommandError):
            return self._handle_git_error(error, stage)
        elif isinstance(error, TimeoutError):
            logger.warning("Operation timed out, will retry...")
            return True

        # For other errors, check if we should retry
        if self.stage_attempts < self.MAX_STAGE_ATTEMPTS - 1:
            # Calculate exponential backoff
            delay = min(self.RETRY_DELAY * (2**self.stage_attempts), 300)  # Max 5 minutes
            logger.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)
            return True

        return False

    def _handle_git_error(self, error: GitCommandError, stage: WorkflowStage) -> bool:
        """Handle Git-specific errors during workflow execution.

        Args:
            error: The GitCommandError that occurred
            stage: The current workflow stage

        Returns:
            bool: True if the error was handled and execution can continue,
                  False if the workflow should stop
        """
        error_msg = str(error).lower()

        # Handle common Git errors
        if "merge conflict" in error_msg:
            conflict_error = ConflictError("Merge conflict detected", conflicts=[])
            return self._handle_conflict(stage, conflict_error)

        elif "authentication failed" in error_msg:
            logger.error("Git authentication failed. Please check your credentials.")
            return False

        elif "connection refused" in error_msg or "could not resolve host" in error_msg:
            logger.warning("Network issue detected, will retry...")
            return True

        # For other Git errors, log and retry
        if self.stage_attempts < self.MAX_STAGE_ATTEMPTS - 1:
            logger.warning(f"Git error occurred, will retry: {error}")
            return True

        return False

    def _handle_stage_failure(self, stage: WorkflowStage) -> None:
        """Handle a stage that has failed after all retry attempts."""
        error_msg = (
            f"Stage {stage.value} failed after {self.MAX_STAGE_ATTEMPTS} attempts. "
            f"Last error: {self.last_error}"
        )
        logger.error(error_msg)

        # Create a recovery branch with the error details
        if self.current_repo:
            self._create_recovery_branch(f"stage-failure-{stage.value}")

        # Update state and save
        self.state = WorkflowState.FAILED
        self._save_state()

        # Re-raise the last error
        raise self.last_error

    def _prepare_repository_for_stage(self, stage: WorkflowStage) -> None:
        """Prepare the repository for a specific workflow stage.

        Args:
            stage: The current workflow stage
        """
        if stage == WorkflowStage.INITIALIZING:
            # Ensure we start with a clean working directory
            self.repo_manager.reset_to_commit(self.current_repo, 'HEAD', hard=True)

        elif stage == WorkflowStage.GENERATING:
            # Create a feature branch for this iteration
            branch_name = f"feature/iteration-{len(self.stage_results.get('iterations', [])) + 1}"
            self.repo_manager.checkout_branch(self.current_repo, branch_name, create=True)

    def _handle_stage_success(self, stage: WorkflowStage, result: Any) -> None:
        """Handle successful stage completion.

        Args:
            stage: The completed workflow stage
            result: Result from the stage function
        """
        # Save the result
        if stage.value not in self.stage_results:
            self.stage_results[stage.value] = {}
        self.stage_results[stage.value] = result

        # Commit changes if this is a significant stage
        if (
            stage
            in [
                WorkflowStage.ANALYZING,
                WorkflowStage.GENERATING,
                WorkflowStage.ADAPTING,
                WorkflowStage.EVALUATING,
            ]
            and self.current_repo
        ):
            commit_msg = f"{stage.value}: {result.get('message', 'Stage completed')}"
            self.repo_manager.commit_changes(self.current_repo, commit_msg)

        # Reset retry counter and save state
        self.retry_count = 0
        self._save_state()

    def _handle_conflict(self, stage: WorkflowStage, conflict: ConflictError) -> bool:
        """Handle merge conflicts during workflow execution.

        Args:
            stage: The current workflow stage
            conflict: The conflict exception

        Returns:
            bool: True if conflict was resolved, False otherwise
        """
        logger.warning(f"Handling conflict in stage {stage.value}")

        try:
            # For now, just abort the merge and let the retry logic handle it
            # In a real implementation, you might want to implement more sophisticated
            # conflict resolution strategies here
            repo = self.repo_manager.get_repository(self.current_repo)
            if repo:
                repo.git.merge('--abort')

            return False  # Let the retry logic handle it

        except Exception as e:
            logger.error(f"Failed to handle conflict: {e}")
            return False

    def request_pause(self) -> bool:
        """Request the workflow to pause after the current stage completes.

        Returns:
            bool: True if the pause was requested, False if already paused or not running
        """
        if self.state == WorkflowState.RUNNING:
            self.pause_requested = True
            logger.info("Pause requested after current stage")
            return True
        return False

    def pause(self) -> bool:
        """Pause the workflow immediately.

        Returns:
            bool: True if the workflow was paused, False otherwise
        """
        if self.state == WorkflowState.RUNNING:
            self.state = WorkflowState.PAUSED
            self._save_state()
            logger.info("Workflow paused")
            return True
        return False

    def resume(self) -> bool:
        """Resume a paused workflow.

        Returns:
            bool: True if the workflow was resumed, False otherwise

        Raises:
            RuntimeError: If there was a previous error that needs to be handled
        """
        if self.state != WorkflowState.PAUSED:
            return False

        if self.last_error:
            raise RuntimeError(
                f"Cannot resume workflow due to previous error: {self.last_error}"
                " Please handle the error and retry."
            )

        self.state = WorkflowState.RUNNING
        logger.info("Workflow resumed")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the workflow.

        Returns:
            Dictionary containing workflow status information
        """
        return {
            "state": self.state.value,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "stage_attempt": self.stage_attempts,
            "last_error": str(self.last_error) if self.last_error else None,
            "repository": self.current_repo,
            "branch": self.current_branch,
            "completed_stages": list(self.stage_results.keys()),
        }

    def _create_recovery_branch(self, reason: str = "recovery") -> bool:
        """Create a recovery branch when workflow fails.

        Args:
            reason: Reason for recovery branch creation

        Returns:
            bool: True if recovery branch was created successfully
        """
        if not self.current_repo:
            return False

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch_name = f"recovery/{reason}-{timestamp}"

            self.repo_manager.checkout_branch(self.current_repo, branch_name, create=True)

            # Commit any uncommitted changes
            self.repo_manager.commit_changes(
                self.current_repo, f"Recovery point: {reason} at {timestamp}"
            )

            logger.info(f"Created recovery branch: {branch_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create recovery branch: {e}")
            return False

    async def run_workflow(
        self, repository_url: str, iterations: int = 5, resume: bool = False
    ) -> List[Dict[str, Any]]:
        """Run the evolution workflow.

        Args:
            repository_url: URL of the repository to evolve.
            iterations: Number of evolution iterations to run.
            resume: Whether to resume from the last saved state.

        Returns:
            List of results from each iteration.
        """
        try:
            # Initialize workflow
            if not resume:
                self._clear_state()

            self.state = WorkflowState.RUNNING
            self._save_state()

            # Initialize repository
            await self._execute_stage(
                WorkflowStage.INITIALIZING, self._initialize_repository, repository_url
            )

            results = []
            for i in range(iterations):
                logger.info(f"Starting evolution iteration {i+1}/{iterations}")

                # Run a single evolution iteration
                result = await self._run_evolution_iteration(i)
                results.append(result)

                # Check if we should continue
                if not result.get("should_continue", True):
                    break

            # Finalize workflow
            await self._execute_stage(WorkflowStage.FINALIZING, self._finalize_workflow)

            self.state = WorkflowState.COMPLETED
            self._save_state()

            return results

        except Exception as e:
            self.state = WorkflowState.FAILED
            self._save_state()
            logger.error(f"Workflow failed: {e}", exc_info=True)
            raise

    async def _initialize_repository(self, repository_url: str) -> Dict[str, Any]:
        """Initialize the repository for evolution.

        This method:
        1. Clones the repository if it doesn't exist locally
        2. Creates a new branch for the evolution workflow
        3. Sets up the initial commit
        4. Configures the repository for the evolution process

        Args:
            repository_url: URL of the repository to evolve.

        Returns:
            Dictionary with initialization results containing:
            - status: "success" or "error"
            - repository: Name of the repository
            - branch: Name of the created branch
            - path: Local path to the repository
            - message: Additional status message
            - commit: Initial commit hash

        Raises:
            RepositoryError: If repository initialization fails
        """
        try:
            # Extract repository name from URL
            repo_name = repository_url.split('/')[-1]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]

            # Check if repository already exists locally
            repo_path = self.work_dir / "repositories" / repo_name

            if repo_path.exists():
                logger.info(f"Using existing repository at {repo_path}")
                # Update the existing repository
                self.repo_manager.pull_changes(repo_name)
            else:
                # Clone the repository
                logger.info(f"Cloning repository from {repository_url}")
                repo_path = self.repo_manager.clone_repository(repository_url, repo_name)

            # Create a new branch for the evolution workflow
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch_name = f"evolve/{timestamp}"

            logger.info(f"Creating evolution branch: {branch_name}")

            # Ensure we're on the default branch first
            default_branch = self.repo_manager.get_default_branch(repo_name)
            self.repo_manager.checkout_branch(repo_name, default_branch)

            # Create and switch to the new branch
            if not self.repo_manager.checkout_branch(repo_name, branch_name, create=True):
                raise RepositoryError(f"Failed to create evolution branch: {branch_name}")

            # Store repository information
            self.current_repo = repo_name
            self.current_branch = branch_name

            # Create initial commit for the evolution branch
            self.repo_manager.commit_changes(
                repo_name,
                f"Initialize evolution workflow on {branch_name}\n\n"
                f"Repository: {repository_url}\n"
                f"Timestamp: {timestamp}",
                allow_empty=True,
            )

            # Get the initial commit hash
            repo = self.repo_manager.get_repository(repo_name)
            initial_commit = repo.head.commit.hexsha[:8]

            logger.info(f"Repository initialized at {repo_path}")

            return {
                "status": "success",
                "repository": self.current_repo,
                "branch": self.current_branch,
                "path": str(repo_path),
                "commit": initial_commit,
                "message": f"Repository initialized successfully on branch {branch_name}",
            }

        except Exception as e:
            error_msg = f"Failed to initialize repository: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Clean up if we partially initialized
            if 'repo_path' in locals() and repo_path.exists() and not self.current_repo:
                logger.warning(f"Cleaning up partially initialized repository at {repo_path}")
                try:
                    shutil.rmtree(repo_path)
                except Exception as cleanup_error:
                    logger.error(f"Error during cleanup: {cleanup_error}")

            return {
                "status": "error",
                "message": error_msg,
                "repository": self.current_repo or "",
                "branch": self.current_branch or "",
            }

    async def _run_evolution_iteration(self, iteration: int) -> Dict[str, Any]:
        """Run a single evolution iteration.

        This method:
        1. Creates a feature branch for the iteration
        2. Runs analysis and generates improvements
        3. Commits changes if they're an improvement
        4. Merges back to main branch if successful

        Args:
            iteration: The current iteration number.

        Returns:
            Dictionary with iteration results.
        """
        iteration_result = {
            "iteration": iteration,
            "success": False,
            "is_improvement": False,
            "stages": {},
        }

        try:
            # Execute each stage of the evolution pipeline
            analysis = await self._execute_stage(
                WorkflowStage.ANALYZING, self.pipeline._analyze_current_version
            )
            iteration_result["stages"]["analysis"] = analysis

            improvements = await self._execute_stage(
                WorkflowStage.GENERATING, self.pipeline._generate_improvements, analysis
            )
            iteration_result["stages"]["improvements"] = improvements

            adapted = await self._execute_stage(
                WorkflowStage.ADAPTING, self.pipeline._adapt_improvements, improvements
            )
            iteration_result["stages"]["adapted_improvements"] = adapted

            evaluation = await self._execute_stage(
                WorkflowStage.EVALUATING, self.pipeline._evaluate_version, adapted
            )
            iteration_result["stages"]["evaluation"] = evaluation

            is_improvement = await self._execute_stage(
                WorkflowStage.VALIDATING, self.pipeline._validate_improvement, evaluation
            )

            iteration_result.update(
                {
                    "success": True,
                    "is_improvement": is_improvement,
                    "should_continue": is_improvement,
                }
            )

            return iteration_result

        except Exception as e:
            logger.error(f"Iteration {iteration} failed: {e}")
            iteration_result["error"] = str(e)
            iteration_result["should_continue"] = False
            return iteration_result

    async def _finalize_workflow(self) -> Dict[str, Any]:
        """Finalize the workflow.

        Returns:
            Dictionary with finalization results.
        """
        logger.info("Finalizing workflow")

        result = {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "repository": None,
            "branch": self.current_branch,
        }

        if self.current_repo:
            try:
                # Commit all changes
                commit_message = (
                    f"EVOSEAL: Final changes from evolution workflow\n"
                    f"Timestamp: {datetime.utcnow().isoformat()}"
                )

                if self.repo_manager.commit_changes(self.current_repo, commit_message):
                    result["repository"] = self.current_repo
                    result["commit"] = self.repo_manager.get_status(self.current_repo).get('commit')
                    logger.info(f"Committed final changes to repository")
                else:
                    result["warning"] = "No changes to commit"

            except Exception as e:
                logger.error(f"Error during workflow finalization: {e}")
                result["error"] = str(e)

        return result


def main():
    """Main entry point for the evolution pipeline."""
    import argparse
    import logging

    # Set up argument parser
    parser = argparse.ArgumentParser(description='EVOSEAL Evolution Pipeline')
    parser.add_argument('--config', required=True, help='Path to configuration file')
    parser.add_argument('--repository', required=True, help='URL of the repository to evolve')
    parser.add_argument('--iterations', type=int, default=5, help='Number of evolution iterations')
    parser.add_argument('--log-level', default='INFO', help='Logging level')

    # Parse arguments
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    try:
        # Create and run workflow coordinator
        coordinator = WorkflowCoordinator(args.config)

        # Run the workflow
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(
            coordinator.run_workflow(args.repository, args.iterations)
        )

        # Print summary
        print(f"\nEvolution completed successfully!")
        print(f"Iterations: {len(results)}")
        print(f"Improvements found: {sum(1 for r in results if r.get('is_improvement', False))}")

    except Exception as e:
        logger.error(f"Evolution failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
