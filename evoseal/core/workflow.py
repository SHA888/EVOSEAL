"""
Workflow Engine Module

This module implements the core WorkflowEngine class that serves as the main interface
for managing and executing workflows in the EVOSEAL system.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

# Type variables for better type safety
T = TypeVar("T")
R = TypeVar("R")

# Type aliases with proper forward references
if TYPE_CHECKING:
    JsonValue: TypeAlias = Any  # Using Any to avoid recursive type issues

    class StepConfig(dict[str, Any]):
        """Configuration for a workflow step."""

    class WorkflowConfig(dict[str, Any]):
        """Configuration for a workflow."""

    EventHandler = Callable[[dict[str, Any]], None]  # Type alias for event handlers
else:
    JsonValue = object
    StepConfig = dict
    WorkflowConfig = dict
    EventHandler = Callable[[dict], None]  # Type alias for event handlers

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Represents the status of a workflow."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class WorkflowEngine:
    """
    Core workflow engine for managing and executing workflows.

    The WorkflowEngine provides a flexible way to define, execute, and monitor
    workflows composed of multiple steps and components. It handles component
    registration, workflow definition, execution, and event handling.

    Args:
        config: Optional configuration dictionary for the workflow engine.

    Attributes:
        config (Dict[str, Any]): Configuration settings for the workflow engine.
        components (Dict[str, Any]): Registered components by name.
        workflows (Dict[str, Dict]): Defined workflows by name.
        status (WorkflowStatus): Current status of the workflow engine.
        event_handlers (Dict[str, List[Callable]]): Registered event handlers.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialize the workflow engine with optional configuration.

        Args:
            config: Optional configuration dictionary for the workflow engine.
        """
        self.config: dict[str, Any] = config or {}
        self.components: dict[str, Any] = {}
        self.workflows: dict[str, Any] = {}  # Using Any to avoid recursive type issues
        self._status: WorkflowStatus = WorkflowStatus.PENDING
        self.event_handlers: dict[str, list[EventHandler]] = {}
        logger.info("WorkflowEngine initialized")

    @property
    def status(self) -> WorkflowStatus:
        """Get the current status of the workflow engine.

        Returns:
            The current workflow status
        """
        return self._status

    @status.setter
    def status(self, value: WorkflowStatus) -> None:
        """Set the status of the workflow engine.

        Args:
            value: The new status to set
        """
        self._status = value

    def register_component(self, name: str, component: object) -> None:
        """
        Register a component with the workflow engine.

        Components are reusable pieces of functionality that can be called from workflow steps.

        Args:
            name: Unique name to identify the component.
            component: The component instance to register.

        Example:
            ```python
            engine.register_component('data_loader', DataLoader())
            ```
        """
        self.components[name] = component
        logger.debug(f"Registered component: {name}")

    def define_workflow(self, name: str, steps: Sequence[StepConfig]) -> None:
        """
        Define a new workflow with the given name and steps.

        A workflow consists of a sequence of steps, where each step specifies
        a component and method to call, along with any parameters.

        Args:
            name: Unique name for the workflow.
            steps: List of step definitions. Each step is a dictionary with:
                - name: Step name for logging
                - component: Name of a registered component
                - method: Method to call on the component (optional, defaults to __call__)
                - params: Dictionary of parameters to pass (optional)

        Example:
            ```python
            workflow = [
                {
                    'name': 'load_data',
                    'component': 'loader',
                    'method': 'load',
                    'params': {'source': 'data.csv'}
                },
                {
                    'name': 'process',
                    'component': 'processor',
                    'method': 'process'
                }
            ]
            engine.define_workflow('data_processing', workflow)
            ```
        """
        self.workflows[name] = {"steps": steps, "status": WorkflowStatus.PENDING}
        logger.info(f"Defined workflow: {name} with {len(steps)} steps")

    def execute_workflow(self, name: str) -> bool:
        """
        Execute a defined workflow by name.

        Executes all steps in the workflow sequentially. If any step fails,
        the workflow is marked as failed and execution stops.

        Args:
            name: Name of the workflow to execute.

        Returns:
            bool: True if the workflow completed successfully, False otherwise.

        Raises:
            KeyError: If the specified workflow does not exist.

        Example:
            ```python
            success = engine.execute_workflow('data_processing')
            if success:
                print("Workflow completed successfully")
            else:
                print("Workflow failed")
            ```
        """
        if name not in self.workflows:
            error_msg = f"Workflow not found: {name}"
            logger.error(error_msg)
            raise KeyError(error_msg)

        workflow = self.workflows[name]
        workflow["status"] = WorkflowStatus.RUNNING
        self.status = WorkflowStatus.RUNNING

        logger.info(f"Starting workflow: {name}")
        self._trigger_event("workflow_started", {"workflow": name})

        try:
            for step in workflow["steps"]:
                self._execute_step(step)

            workflow["status"] = WorkflowStatus.COMPLETED
            self.status = WorkflowStatus.COMPLETED
            logger.info(f"Completed workflow: {name}")
            self._trigger_event("workflow_completed", {"workflow": name})
            return True

        except Exception as e:
            workflow["status"] = WorkflowStatus.FAILED
            self.status = WorkflowStatus.FAILED
            logger.error(f"Workflow {name} failed: {str(e)}", exc_info=True)
            self._trigger_event("workflow_failed", {"workflow": name, "error": str(e)})
            return False

    def _execute_step(self, step: dict[str, Any]) -> Any | None:
        """Execute a single workflow step.

        Args:
            step: Dictionary containing step configuration

        Returns:
            The result of the step execution, or None if no result

        Raises:
            KeyError: If required step configuration is missing
            AttributeError: If component or method is not found
        """
        step_name = str(step.get("name", "unnamed_step"))
        component_name = step.get("component")
        method_name = step.get("method")
        params = step.get("params", {})

        if not isinstance(params, dict):
            params = {}

        logger.debug(f"Executing step: {step_name}")
        self._trigger_event("step_started", {"step": step_name})

        try:
            if component_name and component_name in self.components:
                component = self.components[component_name]
                # Execute component method if specified, otherwise call the component directly
                if method_name and hasattr(component, method_name):
                    method = getattr(component, method_name)
                    if not callable(method):
                        raise AttributeError(
                            f"Method '{method_name}' is not callable on component '{component_name}'"
                        )
                    result = method(**(params or {}))
                elif callable(component):
                    result = component(**(params or {}))
                else:
                    raise AttributeError(
                        f"Component '{component_name}' is not callable and no method specified"
                    )

                logger.debug(f"Step {step_name} completed successfully")
                self._trigger_event(
                    "step_completed", {"step": step_name, "result": result}
                )
                return result
            else:
                error_msg = f"Component not found: {component_name}"
                logger.error(error_msg)
                raise KeyError(error_msg)

        except Exception as e:
            error_msg = f"Step {step_name} failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._trigger_event("step_failed", {"step": step_name, "error": str(e)})
            # Re-raise the exception to be handled by the workflow
            raise

    def register_event_handler(self, event_type: str, handler: EventHandler) -> None:
        """
        Register an event handler for workflow events.

        Event handlers are called when specific events occur during workflow
        execution. The following events are supported:
        - workflow_started: When a workflow starts executing
        - workflow_completed: When a workflow completes successfully
        - workflow_failed: When a workflow fails
        - step_started: When a workflow step starts
        - step_completed: When a workflow step completes
        - step_failed: When a workflow step fails

        Args:
            event_type: Type of event to handle.
            handler: Callable that will be called when the event occurs.
                   The handler should accept a single dictionary argument
                   containing event data.

        Example:
            ```python
            def log_event(event_data):
                print(f"Event: {event_data}")

            engine.register_event_handler('workflow_completed', log_event)
            ```
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def _trigger_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Trigger all handlers for an event type."""
        for handler in self.event_handlers.get(event_type, []):
            try:
                handler(data)
            except Exception as e:
                logger.error(
                    f"Error in event handler for {event_type}: {str(e)}", exc_info=True
                )

    def get_status(self) -> WorkflowStatus:
        """Get the current status of the workflow engine.

        Returns:
            The current workflow status.

        .. deprecated:: 1.0.0
           Use the `status` property instead.
        """
        return self.status
