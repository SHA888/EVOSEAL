"""
Workflow Engine Module

This module implements the core WorkflowEngine class that serves as the main interface
for managing and executing workflows in the EVOSEAL system.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Literal, Optional, TypeAlias, TypeVar, Union, cast

from typing_extensions import TypedDict, NotRequired

from evoseal.core.events import EventBus, Event, EventType

# Type variables
R = TypeVar("R")

# Type aliases with proper forward references
JsonValue: TypeAlias = Any  # Using Any to avoid recursive type issues

# Define handler types
SyncHandler = Callable[[dict[str, Any]], Optional[Any]]
AsyncHandler = Callable[[dict[str, Any]], Awaitable[None]]
EventHandlerType: TypeAlias = Union[SyncHandler, AsyncHandler]

# Define component method types
SyncComponentMethod = Callable[..., Any]
AsyncComponentMethod = Callable[..., Awaitable[Any]]
ComponentMethod: TypeAlias = Union[SyncComponentMethod, AsyncComponentMethod]

# Type alias for backward compatibility
EventHandler: TypeAlias = Callable[[dict[str, Any]], Optional[Any]]

# Logger
logger = logging.getLogger(__name__)


class StepConfig(TypedDict, total=False):
    """Configuration for a workflow step.
    
    Attributes:
        name: Step name for logging and identification.
        component: Name of the registered component to use.
        method: Method to call on the component (defaults to __call__).
        params: Parameters to pass to the component method.
        dependencies: List of step names that must complete before this step runs.
        on_success: Action to take when the step completes successfully.
        on_failure: Action to take when the step fails.
    """
    name: str
    component: str
    method: NotRequired[str]  # Optional, defaults to __call__
    params: NotRequired[Dict[str, Any]]  # Optional parameters
    dependencies: NotRequired[List[str]]  # Optional dependencies
    on_success: NotRequired[Dict[str, Any]]  # Optional success action
    on_failure: NotRequired[Dict[str, Any]]  # Optional failure action


class WorkflowConfig(TypedDict, total=False):
    """Configuration for a workflow.
    
    Attributes:
        name: Unique name for the workflow.
        description: Optional description of the workflow.
        version: Version of the workflow definition.
        steps: List of step configurations.
        parameters: Global parameters available to all steps.
        max_retries: Maximum number of retry attempts for failed steps.
        timeout: Maximum execution time for the workflow.
    """
    name: str
    description: NotRequired[str]  # Optional description
    version: NotRequired[str]  # Optional version
    steps: List[StepConfig]
    parameters: NotRequired[Dict[str, Any]]  # Optional global parameters
    max_retries: NotRequired[int]  # Optional retry limit
    timeout: NotRequired[int]  # Optional timeout in seconds


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
        """Initialize the workflow engine.

        Args:
            config: Optional configuration dictionary for the workflow engine.
        """
        self.config: dict[str, Any] = config or {}
        self.components: dict[str, Any] = {}
        self.workflows: dict[str, Any] = {}
        self._status: WorkflowStatus = WorkflowStatus.PENDING
        self.event_bus: EventBus = EventBus()
        self._local_handlers: dict[str, list[EventHandler]] = {}
        # For storing unsubscribe callbacks
        # These can be either direct unsubscribe functions or decorator functions
        self._event_handlers: list[Callable[[], None]] = []
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

    async def execute_workflow_async(self, name: str) -> bool:
        """
        Asynchronously execute a defined workflow by name.

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
            success = await engine.execute_workflow_async('data_processing')
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

        # Publish workflow started event
        await self.event_bus.publish(
            Event(
                event_type=EventType.WORKFLOW_STARTED,
                source=f"workflow_engine:{id(self)}",
                data={"workflow": name, "timestamp": time.time()},
            )
        )

        try:
            for step in workflow["steps"]:
                await self._execute_step_async(step)

            workflow["status"] = WorkflowStatus.COMPLETED
            self.status = WorkflowStatus.COMPLETED
            logger.info(f"Completed workflow: {name}")

            # Publish workflow completed event
            await self.event_bus.publish(
                Event(
                    event_type=EventType.WORKFLOW_COMPLETED,
                    source=f"workflow_engine:{id(self)}",
                    data={
                        "workflow": name,
                        "timestamp": time.time(),
                        "status": "completed",
                    },
                )
            )
            return True

        except Exception as e:
            workflow["status"] = WorkflowStatus.FAILED
            self.status = WorkflowStatus.FAILED
            error_msg = f"Workflow {name} failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Publish workflow failed event
            await self.event_bus.publish(
                Event(
                    event_type=EventType.WORKFLOW_FAILED,
                    source=f"workflow_engine:{id(self)}",
                    data={
                        "workflow": name,
                        "error": str(e),
                        "timestamp": time.time(),
                        "status": "failed",
                    },
                )
            )
            return False

    def execute_workflow(self, name: str) -> bool:
        """
        Synchronously execute a defined workflow by name.

        This is a synchronous wrapper around execute_workflow_async.

        Args:
            name: Name of the workflow to execute.

        Returns:
            bool: True if the workflow completed successfully, False otherwise.

        Raises:
            KeyError: If the specified workflow does not exist.
        """
        return asyncio.get_event_loop().run_until_complete(
            self.execute_workflow_async(name)
        )

    async def _execute_step_async(self, step: dict[str, Any]) -> Any | None:
        """Execute a single workflow step asynchronously.

        Args:
            step: Dictionary containing step configuration

        Returns:
            The result of the step execution, or None if no result
        """
        step_name = str(step.get("name", "unnamed_step"))
        component_name = step.get("component")
        method_name = step.get("method")
        params = step.get("params", {})

        if not isinstance(params, dict):
            params = {}

        if not component_name:
            error_msg = f"Missing 'component' in step: {step}"
            logger.error(error_msg)
            raise KeyError(error_msg)

        logger.info(f"Executing step: {step_name}")

        # Trigger step started event
        await self.event_bus.publish(
            Event(
                event_type=EventType.STEP_STARTED,
                source=f"workflow_engine:{id(self)}",
                data={"step": step_name, "component": component_name, "params": params},
            )
        )

        try:
            if component_name in self.components:
                component = self.components[component_name]
                method = getattr(component, method_name if method_name else "__call__")

                # Call the component method with parameters
                if asyncio.iscoroutinefunction(method):
                    result = await method(**params) if params else await method()
                else:
                    result = method(**params) if params else method()

                logger.debug(f"Step {step_name} completed successfully")

                # Trigger step completed event
                await self.event_bus.publish(
                    Event(
                        event_type=EventType.STEP_COMPLETED,
                        source=f"workflow_engine:{id(self)}",
                        data={
                            "step": step_name,
                            "component": component_name,
                            "result": result,
                        },
                    )
                )

                return result
            else:
                error_msg = f"Component not found: {component_name}"
                logger.error(error_msg)
                raise KeyError(error_msg)

        except Exception as e:
            error_msg = f"Step {step_name} failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Trigger step failed event
            await self.event_bus.publish(
                Event(
                    event_type=EventType.STEP_FAILED,
                    source=f"workflow_engine:{id(self)}",
                    data={
                        "step": step_name,
                        "component": component_name,
                        "error": str(e),
                        "params": params,
                    },
                )
            )

            # Re-raise the exception to be handled by the workflow
            raise

    def _execute_step(self, step: dict[str, Any]) -> Any | None:
        """Synchronous wrapper for _execute_step_async.
        
        Args:
            step: Dictionary containing step configuration
            
        Returns:
            The result of the step execution, or None if no result
            
        Note:
            Uses asyncio.run() to manage the event loop lifecycle automatically.
            This creates a new event loop for each step execution and closes it properly.
        """
        return asyncio.run(self._execute_step_async(step))

    def register_event_handler(
        self,
        event_type: EventType | str,
        handler: Callable[[dict[str, Any]], Any] | None = None,
        priority: int = 0,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> (
        Callable[[dict[str, Any]], Any]
        | Callable[[Callable[[dict[str, Any]], Any]], Callable[[dict[str, Any]], Any]]
    ):
        """Register an event handler for workflow events.

        This method can be used as a decorator or called directly.

        Event handlers are called when specific events occur during workflow
        execution. The following events are supported:
        - workflow_started: When a workflow starts execution
        - workflow_completed: When a workflow completes successfully
        - workflow_failed: When a workflow fails
        - step_started: When a workflow step starts execution
        - step_completed: When a workflow step completes successfully
        - step_failed: When a workflow step fails

        Args:
            event_type: The type of event to handle
            handler: The handler function (if using as a decorator, leave as None)
            priority: Handler priority (higher = called first)
            filter_fn: Optional filter function to decide whether to call the handler

        Returns:
            The decorator if handler is None, else the handler
        """
        event_type_str = (
            event_type.value if isinstance(event_type, EventType) else str(event_type)
        )

        def decorator(
            handler_func: Callable[[dict[str, Any]], Any],
        ) -> Callable[[dict[str, Any]], Any]:
            # Create a wrapper to pass the event object directly
            def sync_wrapper(event: Event) -> None:
                try:
                    # Pass the event object directly instead of event.data
                    handler_func(event)
                except Exception as e:
                    logger.error(
                        f"Error in sync event handler for {event_type_str}: {e}",
                        exc_info=True,
                    )

            async def async_wrapper(event: Event) -> None:
                try:
                    # Pass the event object directly instead of event.data
                    result = handler_func(event)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(
                        f"Error in async event handler for {event_type_str}: {e}",
                        exc_info=True,
                    )

            # Determine if the handler is async
            is_async = asyncio.iscoroutinefunction(handler_func)
            
            # Choose the appropriate wrapper based on the handler type
            wrapper = async_wrapper if is_async else sync_wrapper

            # Register the handler with the event bus
            unsubscribe = self.event_bus.subscribe(
                event_type=event_type_str,
                handler=wrapper,
                priority=priority,
                filter_fn=filter_fn,
            )

            # Store the unsubscribe function if it's callable
            if callable(unsubscribe):
                if asyncio.iscoroutinefunction(unsubscribe):
                    # For async unsubscribe functions, create a wrapper that runs them in the event loop
                    def async_unsubscribe_wrapper() -> None:
                        asyncio.get_event_loop().run_until_complete(unsubscribe())

                    self._event_handlers.append(async_unsubscribe_wrapper)
                else:
                    # For sync unsubscribe functions, just cast and store directly
                    self._event_handlers.append(cast(Callable[[], None], unsubscribe))

            return handler_func

        # Handle the case when used as a decorator without calling
        if handler is None:
            return decorator

        # Handle the case when called directly
        return decorator(handler)

    def cleanup(self) -> None:
        """Clean up all event handlers.

        This should be called when the workflow engine is no longer needed
        to prevent memory leaks from event handlers.
        """
        for unsubscribe in self._event_handlers:
            try:
                unsubscribe()
            except Exception as e:
                logger.warning(f"Error unsubscribing event handler: {e}", exc_info=True)
        self._event_handlers.clear()
        logger.debug("Cleaned up all event handlers")

    def _publish_event(
        self, event_type: EventType | str, data: dict[str, Any] | None = None
    ) -> None:
        """
        Trigger an event with the given data.

        This method safely publishes events in both synchronous and asynchronous contexts
        by using asyncio.run_coroutine_threadsafe when an event loop is running,
        or asyncio.run when no event loop is available.

        Args:
            event_type: The type of event to trigger
            data: Optional data to include with the event
        """
        if data is None:
            data = {}

        event = Event(
            event_type=(
                event_type.value
                if isinstance(event_type, EventType)
                else str(event_type)
            ),
            source=f"workflow_engine:{id(self)}",
            data=data,
        )

        try:
            # Try to get the running event loop
            loop = asyncio.get_running_loop()
            # Schedule the coroutine in a thread-safe way without waiting for completion
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish(event),
                loop
            )
        except RuntimeError:
            # No running event loop, run synchronously in a new event loop
            asyncio.run(self.event_bus.publish(event))

    def get_status(self) -> WorkflowStatus:
        """Get the current status of the workflow engine.

        Returns:
            The current workflow status.

        .. deprecated:: 1.0.0
           Use the `status` property instead.
        """
        return self.status
