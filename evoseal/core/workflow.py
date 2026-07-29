"""
Workflow Engine Module

This module implements the core WorkflowEngine class that serves as the main interface
for managing and executing workflows in the EVOSEAL system.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from collections.abc import Awaitable, Callable, Sequence
from enum import Enum
from typing import Any, NotRequired, TypeAlias, TypeVar

from typing_extensions import TypedDict

from evoseal.core.events import Event, EventBus, EventType

# Type variable for generic return types
R = TypeVar("R")

# Define handler types
SyncHandler: TypeAlias = Callable[[dict[str, Any]], Any]
AsyncHandler: TypeAlias = Callable[[dict[str, Any]], Awaitable[None]]
EventHandlerType: TypeAlias = SyncHandler | AsyncHandler

# Define component method types
SyncComponentMethod: TypeAlias = Callable[..., Any]
AsyncComponentMethod: TypeAlias = Callable[..., Awaitable[Any]]
ComponentMethod: TypeAlias = SyncComponentMethod | AsyncComponentMethod

# Type alias for backward compatibility
EventHandler = Callable[[dict[str, Any]], Any]

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
    params: NotRequired[dict[str, Any]]  # Optional parameters
    dependencies: NotRequired[list[str]]  # Optional dependencies
    on_success: NotRequired[dict[str, Any]]  # Optional success action
    on_failure: NotRequired[dict[str, Any]]  # Optional failure action


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
    steps: list[StepConfig]
    parameters: NotRequired[dict[str, Any]]  # Optional global parameters
    max_retries: NotRequired[int]  # Optional retry limit
    timeout: NotRequired[int]  # Optional timeout in seconds


class WorkflowStatus(Enum):
    """Status of a workflow."""

    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
        self.workflows: dict[str, dict[str, Any]] = {}
        self.event_bus = EventBus()
        self.status = WorkflowStatus.IDLE
        self._event_handlers: dict[EventType | str, list[dict[str, Any]]] = {}
        self._step_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._step_lock = threading.RLock()
        self._step_active_threads: set[int] = set()
        self._step_active_lock = threading.Lock()
        self._step_shutdown = False
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
        """Asynchronously execute a defined workflow by name.

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
            logger.error(f"Workflow '{name}' not found")
            raise KeyError(f"Workflow '{name}' not found")

        workflow = self.workflows[name]
        logger.info(f"Starting workflow '{name}'")
        self.status = WorkflowStatus.RUNNING

        # Publish workflow started event
        await self._publish_event(
            EventType.WORKFLOW_STARTED, {"workflow": name, "status": "started"}
        )

        try:
            for step in workflow["steps"]:
                await self._execute_step_async(step)

            workflow["status"] = WorkflowStatus.COMPLETED
            self.status = WorkflowStatus.COMPLETED
            logger.info(f"Completed workflow '{name}'")

            # Publish workflow completed event
            await self._publish_event(
                EventType.WORKFLOW_COMPLETED,
                {"workflow": name, "status": "completed"},
            )
            return True

        except Exception as e:
            workflow["status"] = WorkflowStatus.FAILED
            self.status = WorkflowStatus.FAILED
            logger.error(f"Error executing workflow '{name}': {e}", exc_info=True)
            # Publish workflow failed event
            await self._publish_event(
                EventType.WORKFLOW_FAILED,
                {"workflow": name, "error": str(e), "status": "failed"},
            )
            return False

    def execute_workflow(self, name: str) -> bool:
        """Synchronously execute a defined workflow by name.

        This is a synchronous wrapper around execute_workflow_async that uses asyncio.run()
        to manage the event loop lifecycle automatically.

        Args:
            name: Name of the workflow to execute.

        Returns:
            bool: True if the workflow completed successfully, False otherwise.

        Raises:
            KeyError: If the specified workflow does not exist.

        Note:
            Uses asyncio.run() to manage the event loop lifecycle automatically.
            This creates a new event loop for workflow execution and ensures it's
            properly closed afterward.
        """
        return asyncio.run(self.execute_workflow_async(name))

    async def _execute_step_async(self, step: dict[str, Any]) -> Any:
        """Execute a single workflow step asynchronously.

        Args:
            step: Dictionary containing step configuration

        Returns:
            The result of the step execution, or None if no result
        """
        step_name = step.get("name", "unnamed_step")
        component_name = step.get("component")
        method_name = step.get("method", "__call__")
        params = step.get("params", {})

        if not component_name:
            logger.error(f"Step '{step_name}' is missing required 'component' field")
            raise ValueError(f"Step '{step_name}' is missing required 'component' field")

        if component_name not in self.components:
            logger.error(f"Component '{component_name}' not found for step '{step_name}'")
            raise ValueError(f"Component '{component_name}' not found for step '{step_name}'")

        component = self.components[component_name]
        method = getattr(component, method_name, None)

        if not callable(method):
            logger.error(
                f"Method '{method_name}' not found or not callable on component "
                f"'{component_name}' for step '{step_name}'"
            )
            raise ValueError(
                f"Method '{method_name}' not found or not callable on component "
                f"'{component_name}' for step '{step_name}'"
            )

        logger.info(f"Executing step '{step_name}' with component '{component_name}'")
        try:
            # Publish step started event
            await self._publish_event(
                EventType.STEP_STARTED,
                {"step": step_name, "component": component_name},
            )

            # Execute the step
            if asyncio.iscoroutinefunction(method):
                result = await method(**params)
            else:
                result = method(**params)

            # Publish step completed event
            await self._publish_event(
                EventType.STEP_COMPLETED,
                {"step": step_name, "component": component_name, "result": result},
            )

            return result

        except Exception as e:
            logger.error(
                f"Error executing step '{step_name}' with component '{component_name}': {e}",
                exc_info=True,
            )
            # Publish step failed event
            await self._publish_event(
                EventType.STEP_FAILED,
                {
                    "step": step_name,
                    "component": component_name,
                    "error": str(e),
                },
            )
            raise

    def execute_step(self, step: dict[str, Any]) -> Any:
        """Execute a single workflow step.

        Safe to call from both sync contexts and from within a running
        event loop.  When a loop is already running the coroutine is
        offloaded to a persistent single-worker thread so that
        ``asyncio.run()`` is not re-entered.

        .. warning::
           When called from inside a running event loop, the calling
           **thread** blocks until the step completes (via
           ``ThreadPoolExecutor.submit(…).result()``).  Other tasks
           scheduled on the same loop will not progress until this
           method returns — it prevents the ``RuntimeError`` but is
           *not* concurrency-friendly.

        .. note::
           Concurrent top-level calls are serialized by an internal
           lock to prevent concurrent mutation of shared engine state.
           Recursive/nested calls (e.g. a composite step that itself
           calls ``execute_step``) are detected via a per-thread set
           and routed through a temporary thread to avoid deadlock on
           the single-worker executor.

        Args:
            step: Dictionary containing step configuration.

        Returns:
            The result of the step execution.

        Raises:
            RuntimeError: If :meth:`cleanup` has been called.
        """
        # Atomic shutdown check — prevents TOCTOU with cleanup().
        with self._step_active_lock:
            if self._step_shutdown:
                raise RuntimeError(
                    "execute_step() called after cleanup(); the engine is no longer usable"
                )

        tid = threading.current_thread().ident

        # Detect recursive/nested re-entry on the same thread.
        with self._step_active_lock:
            re_entry = tid in self._step_active_threads
            self._step_active_threads.add(tid)

        try:
            if re_entry:
                # Already inside execute_step on this thread — use a
                # temporary thread so the nested step gets its own
                # event loop without touching the main lock or executor.
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as tmp:
                    return tmp.submit(asyncio.run, self._execute_step_async(step)).result()

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            with self._step_lock:
                if loop is not None and loop.is_running():
                    # Offload to the single-worker executor.  Track the
                    # worker thread's ident in _step_active_threads so
                    # that if the step body calls execute_step()
                    # recursively, the nested call is detected as
                    # re-entry and routed to a tmp thread — the worker
                    # never tries to acquire _step_lock.
                    worker_ready = threading.Event()

                    def _run() -> Any:
                        wtid = threading.current_thread().ident
                        with self._step_active_lock:
                            self._step_active_threads.add(wtid)
                        worker_ready.set()
                        try:
                            return asyncio.run(self._execute_step_async(step))
                        finally:
                            with self._step_active_lock:
                                self._step_active_threads.discard(wtid)

                    fut = self._step_executor.submit(_run)
                    worker_ready.wait()
                    return fut.result()

                return asyncio.run(self._execute_step_async(step))
        finally:
            with self._step_active_lock:
                self._step_active_threads.discard(tid)

    async def execute_step_async(self, step: dict[str, Any]) -> Any:
        """Execute a single workflow step asynchronously.

        Public async counterpart of :meth:`execute_step` for callers
        already inside an async context.  Prefer this over calling the
        private ``_execute_step_async`` directly.

        .. note::
           Unlike :meth:`execute_step`, this method does **not** serialize
           concurrent invocations.  Asyncio is single-threaded, so two
           ``await`` calls cannot interleave mid-step, but callers using
           ``asyncio.gather`` or similar concurrency primitives must
           ensure that the steps themselves (or the components they call)
           are safe to run concurrently.

        Args:
            step: Dictionary containing step configuration.

        Returns:
            The result of the step execution.
        """
        return await self._execute_step_async(step)

    async def _on_workflow_event(self, event: Event) -> None:
        """Handle workflow-related events.

        This method is called for events that are published to the event bus.
        It should only handle events that aren't already handled by the direct
        event publishing in the workflow execution methods.

        Args:
            event: The event to handle
        """
        # Skip handling events that are already handled by direct publishing
        # in the workflow execution methods
        if event.source == "workflow_engine":
            return

        try:
            event_data = event.data or {}
            if event.event_type == EventType.WORKFLOW_STARTED:
                logger.info(f"Workflow started: {event_data.get('workflow')}")
            elif event.event_type == EventType.WORKFLOW_COMPLETED:
                logger.info(f"Workflow completed: {event_data.get('workflow')}")
            elif event.event_type == EventType.WORKFLOW_FAILED:
                logger.error(
                    f"Workflow failed: {event_data.get('workflow')}. "
                    f"Error: {event_data.get('error')}"
                )
            elif event.event_type == EventType.STEP_STARTED:
                logger.debug(
                    f"Step started: {event_data.get('step')} "
                    f"(component: {event_data.get('component')})"
                )
            elif event.event_type == EventType.STEP_COMPLETED:
                logger.debug(
                    f"Step completed: {event_data.get('step')} "
                    f"(component: {event_data.get('component')})"
                )
            elif event.event_type == EventType.STEP_FAILED:
                logger.error(
                    f"Step failed: {event_data.get('step')} "
                    f"(component: {event_data.get('component')}). "
                    f"Error: {event_data.get('error')}"
                )
        except Exception as e:
            logger.error(f"Error handling workflow event {event.event_type}: {e}", exc_info=True)

    def register_event_handler(
        self,
        event_type: EventType | str,
        handler: Callable[[Event], Any] | None = None,
        priority: int = 0,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> Callable[[Event], Any] | Callable[[Callable[[Event], Any]], Callable[[Event], Any]]:
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

        def decorator(
            handler_func: Callable[[Event], Any],
        ) -> Callable[[Event], Any]:
            # Convert event_type to string if it's an Enum
            event_type_str = (
                event_type.value if isinstance(event_type, EventType) else str(event_type)
            )

            # Create a wrapper that will handle the event
            def event_wrapper(event: Event) -> None:
                try:
                    # Apply filter if provided
                    if filter_fn is None or filter_fn(event):
                        handler_func(event)
                except Exception as e:
                    logger.error(
                        f"Error in event handler for {event_type_str}: {e}",
                        exc_info=True,
                    )

            # Register the wrapper with the event bus
            unsubscribe = self.event_bus.subscribe(event_type_str, event_wrapper)

            # Initialize the event type in the handlers dict if needed
            if event_type_str not in self._event_handlers:
                self._event_handlers[event_type_str] = []

            # Store the unsubscribe function with the wrapper
            self._event_handlers[event_type_str].append(
                {
                    "handler": event_wrapper,
                    "unsubscribe": unsubscribe,
                    "priority": priority,
                }
            )

            # Sort handlers by priority (highest first)
            self._event_handlers[event_type_str].sort(key=lambda x: x["priority"], reverse=True)

            logger.debug(f"Registered event handler for {event_type_str} with priority {priority}")
            return handler_func

        # Handle the case when used as a decorator without calling
        if handler is None:
            return decorator

        # Handle the case when called directly
        return decorator(handler)

    def __enter__(self) -> WorkflowEngine:
        """Enter the context manager."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Exit the context manager, cleaning up resources."""
        self.cleanup()

    def cleanup(self) -> None:
        """Clean up all event handlers and the step executor.

        This should be called when the workflow engine is no longer needed
        to prevent memory leaks from event handlers and the background
        worker thread.  Can also be used as a context manager:

            with WorkflowEngine() as engine:
                ...

        After cleanup, :meth:`execute_step` raises ``RuntimeError``.
        """
        for handlers in self._event_handlers.values():
            for handler in handlers:
                handler["unsubscribe"]()
        self._event_handlers.clear()
        # Atomically set shutdown flag under the same lock that
        # execute_step uses to check it, preventing a TOCTOU race
        # where a concurrent caller passes the check before the flag
        # is set but then submits to the already-shut-down executor.
        with self._step_active_lock:
            self._step_shutdown = True
        # Wait for any in-flight offloaded call to finish before shutting
        # the executor down. execute_step holds _step_lock for the full
        # duration of its offload-and-wait critical section, so acquiring
        # it here closes the remaining race: a call that already passed
        # the shutdown check and is submitting to (or awaiting) the
        # executor would otherwise hit "cannot schedule new futures after
        # shutdown" instead of completing normally.
        with self._step_lock:
            self._step_executor.shutdown(wait=False)
        logger.debug("Cleaned up all event handlers")

    async def _publish_event(
        self, event_type: EventType | str, data: dict[str, Any] | None = None
    ) -> None:
        """Publish an event to all registered handlers.

        This is a helper method to publish events in a type-safe way.

        Args:
            event_type: The type of event to publish
            data: Optional data to include with the event
        """
        event_data = data or {}
        event_type_str = event_type.value if isinstance(event_type, EventType) else str(event_type)

        event = Event(
            event_type=event_type_str,
            source="workflow_engine",
            data=event_data,
        )

        logger.debug(f"Publishing event: {event_type_str} with data: {event_data}")

        try:
            # Always use the event bus to publish the event
            # The event bus will handle the async/sync nature of handlers
            await self.event_bus.publish(event)
            logger.debug(f"Successfully published event: {event_type_str}")
        except Exception as e:
            logger.error(f"Error publishing event {event_type_str}: {e}", exc_info=True)
            raise

    def get_status(self) -> WorkflowStatus:
        """Get the current status of the workflow engine.

        Returns:
            The current workflow status.

        .. deprecated:: 1.0.0
           Use the `status` property instead.
        """
        return self.status
