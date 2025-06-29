"""Workflow validation module.

This module provides functionality to validate workflow definitions against a schema
and perform semantic validation of workflow structures.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft7Validator
from jsonschema import ValidationError as JSONSchemaValidationError

# Import Validator type
from .validation_types import JSONArray, JSONObject, JSONValue, ValidationLevel, ValidationResult
from .validation_types import Validator as ValidatorType

# Configure logging
logger = logging.getLogger(__name__)


class WorkflowValidationError(Exception):
    """Raised when a workflow fails validation."""

    def __init__(
        self,
        message: str,
        validation_result: ValidationResult | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the exception.

        Args:
            message: The error message.
            validation_result: Optional validation result with details.
            **kwargs: Additional context for the error.
        """
        self.message = message
        self.validation_result = validation_result or ValidationResult()

        # Always process 'errors' from kwargs, regardless of existing issues
        if "errors" in kwargs and kwargs["errors"]:
            for error in kwargs["errors"]:
                self.validation_result.add_error(
                    error.get("message", "Unknown error"),
                    code=error.get("code", "unknown_error"),
                    path=error.get("path"),
                )

        super().__init__(self.message)


class WorkflowValidator:
    """Validates workflow definitions against a schema and semantic rules."""

    def __init__(self, schema_path: str | Path | None = None, load_schema: bool = True) -> None:
        """Initialize the workflow validator.

        Args:
            schema_path: Optional path to a custom schema file.
            load_schema: Whether to load the schema on initialization.
        """
        self.schema_path = (
            Path(schema_path)
            if schema_path
            else Path(__file__).parent.parent / "schemas" / "workflow_schema.json"
        )
        self.validator: Draft7Validator | None = None
        self._validators: list[ValidatorType] = []

        if load_schema:
            self._load_schema()

    def register_validator(self, validator: ValidatorType) -> None:
        """Register a custom validator function.

        Args:
            validator: A function that takes a workflow and ValidationResult.
        """
        self._validators.append(validator)

    def _load_schema(self) -> None:
        """Load the JSON schema from file."""
        try:
            with open(self.schema_path) as f:
                schema = json.load(f)
            self.validator = Draft7Validator(schema)
        except (json.JSONDecodeError, OSError) as e:
            raise WorkflowValidationError(f"Failed to load schema: {e}") from e

    def _parse_workflow_definition(
        self, workflow_definition: dict[str, Any] | str | Path
    ) -> dict[str, Any]:
        """Parse a workflow definition from various input types.

        Args:
            workflow_definition: The workflow definition to parse.
                Can be a dictionary, JSON string, or file path.

        Returns:
            The parsed workflow as a dictionary.

        Raises:
            WorkflowValidationError: If the workflow cannot be parsed.
        """
        if isinstance(workflow_definition, (str, Path)):
            try:
                # Check if it's a file path
                path = Path(workflow_definition)
                if path.exists() and path.is_file():
                    with open(path, encoding="utf-8") as f:
                        workflow_definition = json.load(f)
                else:
                    # Try to parse as JSON string
                    if not isinstance(workflow_definition, (str, bytes, bytearray)):
                        workflow_definition = str(workflow_definition)
                    workflow_definition = json.loads(workflow_definition)
            except json.JSONDecodeError as e:
                raise WorkflowValidationError(
                    f"Invalid JSON: {e}",
                    code="invalid_json",
                ) from e
            except Exception as e:
                raise WorkflowValidationError(
                    f"Failed to parse workflow: {e}",
                    code="parse_error",
                ) from e

        if not isinstance(workflow_definition, dict):
            raise WorkflowValidationError(
                "Workflow must be a JSON object",
                code="invalid_workflow_type",
            )

        # Ensure we have a proper JSONObject (Dict[str, Any])
        if not all(isinstance(k, str) for k in workflow_definition.keys()):
            raise WorkflowValidationError(
                "Workflow keys must be strings",
                code="invalid_key_type",
            )

        return workflow_definition

    def _validate_schema(
        self, workflow: dict[str, Any], result: ValidationResult, partial: bool = False
    ) -> bool:
        """Validate the workflow against the JSON schema.

        Args:
            workflow: The workflow to validate.
            result: The validation result to populate.
            partial: Whether to stop after the first error.

        Returns:
            bool: True if the workflow is valid against the schema.
        """
        if not self.validator:
            self._load_schema()
            if not self.validator:
                result.add_error(
                    message="Failed to load schema validator",
                    code="schema_validation_error",
                )
                return False

        try:
            self.validator.validate(workflow)
            return True
        except JSONSchemaValidationError:
            errors = list(self.validator.iter_errors(workflow))
            for error in errors:
                # Convert JSON pointer to a dot path
                path = ".".join(str(p) for p in error.absolute_path)
                result.add_error(
                    message=str(error.message),
                    code=error.validator or "schema_validation_error",
                    path=path,
                    context={"value": error.instance},
                )
                if partial:
                    break
            return not errors
        except Exception as e:
            result.add_error(
                message=f"Schema validation failed: {e}",
                code="schema_validation_error",
            )
            return False

    def _validate_semantics(
        self,
        workflow: dict[str, Any],
        result: ValidationResult,
        level: ValidationLevel | str,
        partial: bool = False,
    ) -> bool:
        """Perform semantic validation of the workflow.

        Args:
            workflow: The workflow to validate.
            result: The validation result to populate.
            level: The validation level to use.
            partial: Whether to stop after the first error.

        Returns:
            bool: True if the workflow is semantically valid.
        """
        if isinstance(level, str):
            level_enum = ValidationLevel[level.upper()]
        else:
            level_enum = level

        if level_enum == ValidationLevel.SCHEMA_ONLY:
            return True

        is_valid = self._validate_basic(workflow, result, partial)
        if level_enum == ValidationLevel.FULL and (is_valid or not partial):
            is_valid = self._run_custom_validators(workflow, result, partial) and is_valid
        return is_valid

    @dataclass
    class ValidationContext:
        """Context for workflow validation."""

        task_name: str
        task: dict[str, Any]
        task_names: set[str]
        result: ValidationResult
        partial: bool = False
        action_type: str | None = None

    def _check_circular_dependencies(
        self,
        tasks: dict[str, dict[str, Any]],
        result: ValidationResult,
        partial: bool = False,
    ) -> bool:
        """Check for circular dependencies in the workflow tasks.

        Args:
            tasks: Dictionary of task definitions.
            result: The validation result to populate.
            partial: Whether to stop after the first error.

        Returns:
            bool: True if no circular dependencies are found.
        """
        visited: set[str] = set()
        recursion_stack: set[str] = set()
        cycles: list[list[str]] = []

        def has_cycle(task_name: str, path: list[str]) -> bool:
            if task_name in recursion_stack:
                cycle = path[path.index(task_name) :] + [task_name]
                cycles.append(cycle)
                return True
            if task_name in visited:
                return False

            visited.add(task_name)
            recursion_stack.add(task_name)
            path.append(task_name)

            task = tasks.get(task_name, {})
            for dep in task.get("dependencies", []):
                if dep in tasks and has_cycle(dep, path.copy()):
                    if partial:
                        return True

            recursion_stack.remove(task_name)
            path.pop()
            return False

        for task_name in tasks:
            if has_cycle(task_name, []):
                if partial:
                    break

        if cycles:
            for cycle in cycles:
                cycle_str = " -> ".join(cycle)
                result.add_error(
                    f"Circular dependency detected: {cycle_str}",
                    code="circular_dependency",
                    path=f"tasks.{cycle[0]}",
                )
                if partial:
                    break
            return False

        return True

    @dataclasses.dataclass
    class DependencyValidationContext:
        """Context for validating task dependencies."""

        task_name: str
        task: dict[str, Any]
        task_names: set[str]
        result: ValidationResult
        partial: bool = False

    def _validate_dependencies(self, ctx: DependencyValidationContext) -> bool:
        """Validate task dependencies.

        Args:
            ctx: The dependency validation context.

        Returns:
            bool: True if all dependencies are valid.
        """
        is_valid = True
        for i, dep in enumerate(ctx.task.get("dependencies", [])):
            if dep not in ctx.task_names:
                ctx.result.add_error(
                    f"undefined task '{dep}'",
                    code="undefined_reference",
                    path=f"tasks.{ctx.task_name}.dependencies.{i}",
                )
                is_valid = False
                if ctx.partial:
                    return False
        return is_valid

    def _validate_action(self, ctx: ValidationContext) -> bool:
        """Validate a single action (on_success or on_failure).

        Args:
            ctx: Validation context containing task and action information.

        Returns:
            bool: True if the action is valid.
        """
        if ctx.action_type is None or ctx.action_type not in ctx.task:
            return True

        action = ctx.task[ctx.action_type]
        if not action:
            return True

        # Handle both string and list of objects formats
        if isinstance(action, str):
            # String format - validate it's a valid task reference
            if action not in ctx.task_names and action != "end":
                ctx.result.add_error(
                    f"{ctx.action_type} references undefined task: {action}",
                    path=f"tasks.{ctx.task_name}.{ctx.action_type}",
                )
                return False
            return True
        elif isinstance(action, list):
            # List of objects format - validate each action
            valid = True
            for i, action_item in enumerate(action):
                if not isinstance(action_item, dict):
                    ctx.result.add_error(
                        f"{ctx.action_type} action at index {i} must be an object",
                        path=f"tasks.{ctx.task_name}.{ctx.action_type}[{i}]",
                    )
                    valid = False
                    continue

                next_task = action_item.get("next")
                if next_task and next_task not in ctx.task_names and next_task != "end":
                    ctx.result.add_error(
                        f"{ctx.action_type} action at index {i} references undefined task: {next_task}",
                        path=f"tasks.{ctx.task_name}.{ctx.action_type}[{i}].next",
                    )
                    valid = False

            return valid
        else:
            # Invalid format
            ctx.result.add_error(
                f"{ctx.action_type} must be a string or a list of objects",
                path=f"tasks.{ctx.task_name}.{ctx.action_type}",
            )
            return False

    def _check_undefined_references(
        self,
        tasks: dict[str, dict[str, Any]],
        result: ValidationResult,
        partial: bool = False,
    ) -> bool:
        """Check for undefined task references in dependencies and next steps.

        Args:
            tasks: Dictionary of task definitions.
            result: The validation result to populate.
            partial: Whether to stop after the first error.

        Returns:
            bool: True if all references are defined.
        """
        task_names = set(tasks.keys())
        task_names.add("end")  # 'end' is a special task name
        is_valid = True

        for task_name, task in tasks.items():
            # Check dependencies
            deps_ctx = self.DependencyValidationContext(
                task_name=task_name,
                task=task,
                task_names=task_names,
                result=result,
                partial=partial,
            )
            deps_valid = self._validate_dependencies(deps_ctx)
            if not deps_valid and partial:
                return False
            is_valid = is_valid and deps_valid

            # Create a base context for this task
            ctx = self.ValidationContext(
                task_name=task_name,
                task=task,
                task_names=task_names,
                result=result,
                partial=partial,
            )

            # Check on_success and on_failure actions
            for action_type in ["on_success", "on_failure"]:
                action_ctx = dataclasses.replace(ctx, action_type=action_type)
                action_valid = self._validate_action(action_ctx)
                if not action_valid and partial:
                    return False
                is_valid = is_valid and action_valid

        return is_valid

    def _validate_basic(
        self, workflow: dict[str, Any], result: ValidationResult, partial: bool = False
    ) -> bool:
        """Perform basic semantic validation.

        Args:
            workflow: The workflow to validate.
            result: The validation result to populate.
            partial: Whether to stop after the first error.

        Returns:
            bool: True if the workflow passes basic validation.
        """
        # Check tasks exist and have required fields
        tasks_data = workflow.get("tasks")
        if not isinstance(tasks_data, dict):
            result.add_error(
                "Workflow must have a 'tasks' object with task definitions",
                code="invalid_tasks",
            )
            return False

        # Type check and cast tasks to the expected type
        tasks: dict[str, dict[str, Any]] = {}
        for task_name, task in tasks_data.items():
            if isinstance(task, dict):
                tasks[task_name] = task

        # Check for circular dependencies
        if tasks and not self._check_circular_dependencies(tasks, result, partial):
            if partial:
                return False

        # Check for undefined references
        if tasks and not self._check_undefined_references(tasks, result, partial):
            if partial:
                return False

        return len(result.issues) == 0

    def _run_custom_validators(
        self, workflow: dict[str, Any], result: ValidationResult, partial: bool = False
    ) -> bool:
        """Run all registered custom validators.

        Args:
            workflow: The workflow to validate.
            result: The validation result to populate.
            partial: Whether to stop after the first error.

        Returns:
            bool: True if all custom validators pass.
        """
        is_valid = True
        for validator in self._validators:
            try:
                validator(workflow, result)
                if not result.is_valid and partial:
                    return False
            except Exception as e:
                result.add_error(
                    f"Validator failed: {e}",
                    code="validator_error",
                )
                is_valid = False
                if partial:
                    return False
        return is_valid

    def validate(
        self,
        workflow_definition: dict[str, Any] | str | Path,
        level: ValidationLevel | str = ValidationLevel.FULL,
        partial: bool = False,
    ) -> ValidationResult:
        """Validate a workflow definition.

        Args:
            workflow_definition: The workflow to validate.
            level: The validation level to use.
            partial: Whether to stop after the first error.

        Returns:
            A ValidationResult with any issues found.
        """
        result = ValidationResult()

        try:
            # Parse the workflow definition
            workflow = self._parse_workflow_definition(workflow_definition)

            # Validate against schema
            if not self._validate_schema(workflow, result, partial):
                return result

            # Perform semantic validation
            self._validate_semantics(workflow, result, level, partial)

        except WorkflowValidationError as e:
            result.add_error(
                str(e),
                code="validation_error",
                exception=e,
            )
        except Exception as e:
            result.add_error(
                f"Unexpected error during validation: {e}",
                code="unexpected_error",
                exception=e,
            )

        return result

    async def validate_async(
        self,
        workflow_definition: dict[str, Any] | str | Path,
        level: ValidationLevel | str = ValidationLevel.FULL,
        partial: bool = False,
    ) -> ValidationResult:
        """Asynchronously validate a workflow definition.

        This is an async version of the validate method.

        Args:
            workflow_definition: The workflow to validate.
            level: The validation level to use.
            partial: Whether to stop after the first error.

        Returns:
            ValidationResult: The validation result.
        """
        return await asyncio.to_thread(self.validate, workflow_definition, level, partial)


def validate_workflow(
    workflow_definition: dict[str, Any] | str | Path,
    level: ValidationLevel | str = ValidationLevel.FULL,
    partial: bool = False,
    strict: bool = True,
) -> bool | ValidationResult:
    """Convenience function to validate a workflow.

    Args:
        workflow_definition: The workflow to validate.
        level: The validation level to use.
        partial: Whether to stop after the first error.
        strict: If True, raises an exception on error.

    Returns:
        bool: If strict=True, returns True if valid.
        ValidationResult: If strict=False, returns the full result.

    Raises:
        WorkflowValidationError: If validation fails and strict=True.
    """
    validator = WorkflowValidator()
    try:
        result = validator.validate(workflow_definition, level, partial)
        if strict and not result.is_valid:
            raise WorkflowValidationError(
                "Workflow validation failed",
                validation_result=result,
            )
        return result.is_valid if strict else result
    except Exception as e:
        if strict:
            if isinstance(e, WorkflowValidationError):
                raise
            raise WorkflowValidationError(str(e)) from e
        result = ValidationResult()
        result.add_error(
            str(e),
            code="validation_error",
            exception=e,
        )
        return result


async def validate_workflow_async(
    workflow_definition: dict[str, Any] | str | Path,
    level: ValidationLevel | str = ValidationLevel.FULL,
    partial: bool = False,
    strict: bool = True,
) -> bool | ValidationResult:
    """Async version of validate_workflow.

    Args:
        workflow_definition: The workflow to validate.
        level: The validation level to use.
        partial: Whether to stop after the first error.
        strict: If True, raises an exception on error.

    Returns:
        bool: If strict=True, returns True if valid.
        ValidationResult: If strict=False, returns the full result.

    Raises:
        WorkflowValidationError: If validation fails and strict=True.
    """
    validator = WorkflowValidator()
    try:
        result = await validator.validate_async(workflow_definition, level, partial)
        if strict and not result.is_valid:
            raise WorkflowValidationError(
                "Workflow validation failed",
                validation_result=result,
            )
        return result.is_valid if strict else result
    except Exception as e:
        if strict:
            if isinstance(e, WorkflowValidationError):
                raise
            raise WorkflowValidationError(str(e)) from e
        result = ValidationResult()
        result.add_error(
            str(e),
            code="validation_error",
            exception=e,
        )
        return result


def validate_workflow_schema(workflow_definition: dict[str, Any] | str | Path) -> bool:
    """Quickly validate a workflow against just the schema.

    Args:
        workflow_definition: The workflow to validate.

    Returns:
        bool: True if the workflow is valid against the schema.

    Raises:
        WorkflowValidationError: If the workflow is invalid against the schema.
    """
    validator = WorkflowValidator()
    result = ValidationResult()
    try:
        workflow = validator._parse_workflow_definition(workflow_definition)
        is_valid = validator._validate_schema(workflow, result)
        if not is_valid:
            raise WorkflowValidationError(
                "Workflow validation failed against schema",
                validation_result=result,
            )
        return True
    except WorkflowValidationError:
        raise
    except Exception as e:
        raise WorkflowValidationError(f"Failed to validate workflow schema: {e}") from e


async def validate_workflow_schema_async(
    workflow_definition: dict[str, Any] | str | Path,
) -> bool:
    """Async version of validate_workflow_schema.

    Args:
        workflow_definition: The workflow to validate.

    Returns:
        bool: True if the workflow is valid against the schema.

    Raises:
        WorkflowValidationError: If the workflow is invalid against the schema.
    """
    validator = WorkflowValidator()
    result = ValidationResult()
    try:
        workflow = await asyncio.to_thread(
            validator._parse_workflow_definition, workflow_definition
        )
        is_valid = validator._validate_schema(workflow, result)
        if not is_valid:
            raise WorkflowValidationError(
                "Workflow validation failed against schema",
                validation_result=result,
            )
        return True
    except WorkflowValidationError:
        raise
    except Exception as e:
        raise WorkflowValidationError(f"Failed to validate workflow schema: {e}") from e
