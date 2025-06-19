"""Unit tests for the enhanced workflow validator."""

import asyncio
import os
import sys
from collections.abc import Callable, Coroutine
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar
from unittest.mock import MagicMock, patch

import pytest
from _pytest.fixtures import FixtureRequest
from _pytest.python import Function

from evoseal.utils.validation_types import JSONObject
from evoseal.utils.validator import (
    ValidationLevel,
    ValidationResult,
    WorkflowValidationError,
    WorkflowValidator,
    validate_workflow,
    validate_workflow_async,
    validate_workflow_schema,
    validate_workflow_schema_async,
)

# Type variable for test function return type
T = TypeVar("T")

# Type for async test functions
AsyncTestFunc = Callable[..., Coroutine[Any, Any, T]]

# Type for sync wrapper functions
SyncTestFunc = Callable[..., T]


def async_test(func: AsyncTestFunc[None]) -> Callable[..., None]:
    """Type-safe decorator to run async test functions.

    This decorator converts an async test function into a synchronous one that
    can be run by pytest. It's specifically typed for test functions that return None.

    Args:
        func: The async test function to decorate (should return None)

    Returns:
        A synchronous wrapper function that runs the async test
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(func(*args, **kwargs))

    # Copy pytest markers if they exist
    if hasattr(func, "pytestmark"):
        wrapper.pytestmark = func.pytestmark  # type: ignore[attr-defined]

    return wrapper


# Only mark async tests with asyncio
pytestmark = pytest.mark.asyncio(scope="function")

# Sample valid workflow for testing
SAMPLE_WORKFLOW: JSONObject = {
    "version": "1.0.0",
    "name": "test_workflow",
    "description": "A test workflow",
    "tasks": {
        "task1": {
            "type": "test",
            "description": "First task",
            "action": "test_action",
            "inputs": {"param1": "value1"},
            "on_success": [{"next": "task2"}],
        },
        "task2": {
            "type": "test",
            "description": "Second task",
            "action": "another_action",
            "dependencies": ["task1"],
            "on_success": [{"next": "task3"}],
        },
        "task3": {
            "type": "test",
            "description": "Final task",
            "action": "final_action",
            "dependencies": ["task2"],
        },
    },
}

# Invalid workflow with circular dependency
INVALID_WORKFLOW: JSONObject = {
    "version": "1.0.0",
    "name": "invalid_workflow",
    "tasks": {
        "task1": {
            "type": "test",
            "action": "test_action",
            "dependencies": ["task3"],
        },
        "task2": {
            "type": "test",
            "action": "another_action",
            "dependencies": ["task1"],
        },
        "task3": {
            "type": "test",
            "action": "final_action",
            "dependencies": ["task2"],
        },
    },
}


class TestWorkflowValidator:
    """Test cases for the WorkflowValidator class."""

    def __init__(self) -> None:
        """Initialize test class with type hints."""
        self.validator: WorkflowValidator
        self.valid_workflow: dict[str, Any]

    @pytest.fixture(autouse=True)  # type: ignore[misc]
    def setup(self) -> None:
        """Set up test fixtures."""
        self.validator = WorkflowValidator()
        self.valid_workflow = {
            "name": "test_workflow",
            "version": "1.0.0",
            "tasks": {
                "task1": {
                    "action": {
                        "type": "python",
                        "module": "test_module",
                        "function": "test_function",
                    },
                    "next": "task2",
                },
                "task2": {
                    "action": {
                        "type": "python",
                        "module": "test_module",
                        "function": "another_function",
                    },
                    "next": "end",
                },
            },
        }

    def test_validate_valid_workflow(self) -> None:
        """Test validation of a valid workflow."""
        workflow: dict[str, Any] = {
            "version": "1.0.0",
            "name": "test_workflow",
            "description": "A test workflow",
            "tasks": {
                "task1": {
                    "type": "test",
                    "description": "Test task",
                    "action": "test_action",
                    "dependencies": [],
                    "on_success": [{"next": "end"}],
                    "on_failure": [{"next": "end"}],
                }
            },
        }
        result = self.validator.validate(workflow)
        assert result.is_valid
        assert not result.issues

    def test_validate_invalid_schema(self) -> None:
        """Test validation of a workflow with an invalid schema."""
        invalid: dict[str, Any] = {"version": "1.0"}  # Missing required fields
        result = self.validator.validate(invalid)
        assert not result.is_valid
        assert result.issues
        assert any("required" in str(issue) for issue in result.issues)

        # Test with different validation levels
        result = self.validator.validate(invalid, level=ValidationLevel.SCHEMA_ONLY)
        assert not result.is_valid

    def test_validate_circular_dependency(self) -> None:
        """Test detection of circular dependencies."""
        workflow: JSONObject = INVALID_WORKFLOW  # Contains circular dependencies

        # Should pass with schema-only validation
        result = self.validator.validate(workflow, level=ValidationLevel.SCHEMA_ONLY)
        assert result.is_valid

        # Should fail with basic or full validation
        result = self.validator.validate(workflow, level=ValidationLevel.BASIC)
        assert not result.is_valid
        assert any("circular" in str(issue).lower() for issue in result.issues)

        result = self.validator.validate(workflow, level=ValidationLevel.FULL)
        assert not result.is_valid
        assert any("circular" in str(issue).lower() for issue in result.issues)

    def test_validate_undefined_task_reference(self) -> None:
        """Test detection of undefined task references."""
        workflow: dict[str, Any] = {
            "version": "1.0.0",
            "name": "test_workflow",
            "description": "A test workflow with undefined reference",
            "tasks": {
                "task1": {
                    "type": "test",
                    "description": "Test task with undefined dependency",
                    "action": "test_action",
                    "dependencies": ["nonexistent"],
                    "on_success": [{"next": "end"}],
                    "on_failure": [{"next": "end"}],
                }
            },
        }
        # Should fail with FULL validation
        result = self.validator.validate(workflow, level=ValidationLevel.FULL)
        assert not result.is_valid
        assert any("nonexistent" in str(issue) for issue in result.issues)

        # Should pass with SCHEMA_ONLY validation
        result = self.validator.validate(workflow, level=ValidationLevel.SCHEMA_ONLY)
        assert result.is_valid

    def test_validate_partial(self) -> None:
        """Test partial validation skips some checks."""
        # This workflow has an undefined task reference but we're doing partial validation
        workflow: dict[str, Any] = {
            "version": "1.0.0",  # Must match the semantic versioning pattern in schema
            "name": "test",
            "tasks": {
                "task1": {
                    "type": "task",
                    "action": "test",
                    "on_success": [{"next": "nonexistent"}],
                }
            },
        }
        validator = WorkflowValidator()

        # With partial=True, should still fail schema validation
        result = validator.validate(workflow, level=ValidationLevel.FULL, partial=True)
        assert not result.is_valid

        # With SCHEMA_ONLY level, should pass
        result = validator.validate(
            workflow, level=ValidationLevel.SCHEMA_ONLY, partial=True
        )
        assert result.is_valid

    @pytest.mark.asyncio  # type: ignore[misc]
    @async_test
    async def test_validate_async(self) -> None:
        """Test async validation."""
        result = await self.validator.validate_async(self.valid_workflow)
        assert result.is_valid
        assert not result.issues

    def test_register_custom_validator(self, request: FixtureRequest) -> None:
        """Test registering a custom validator."""

        def custom_validator(
            workflow: dict[str, Any], result: ValidationResult
        ) -> None:
            if workflow.get("name") == "invalid":
                result.add_error("Invalid workflow name", code="invalid_name")

        validator = WorkflowValidator()
        validator.register_validator(custom_validator)

        # Should be valid
        result = validator.validate(SAMPLE_WORKFLOW)
        assert result.is_valid

        # Should be invalid due to our custom validator
        invalid_workflow = SAMPLE_WORKFLOW.copy()
        invalid_workflow["name"] = "invalid"
        result = validator.validate(invalid_workflow)
        assert not result.is_valid
        assert any(e.code == "invalid_name" for e in result.issues)


class TestConvenienceFunctions:
    """Test the convenience functions."""

    def test_validate_workflow_strict(self) -> None:
        """Test the validate_workflow function in strict mode."""
        # Should not raise
        assert validate_workflow(SAMPLE_WORKFLOW, strict=True) is True

        # Should raise
        with pytest.raises(WorkflowValidationError):
            validate_workflow({"invalid": "workflow"}, strict=True)

    def test_validate_workflow_non_strict(self) -> None:
        """Test the validate_workflow function in non-strict mode."""
        result = validate_workflow(SAMPLE_WORKFLOW, strict=False)
        assert isinstance(result, ValidationResult)
        assert result.is_valid

        result = validate_workflow({"invalid": "workflow"}, strict=False)
        assert isinstance(result, ValidationResult)
        assert not result.is_valid

    @pytest.mark.asyncio  # type: ignore[misc]
    @async_test
    async def test_validate_workflow_async(self) -> None:
        """Test the async validate_workflow_async function."""
        # Should not raise
        result = await validate_workflow_async(SAMPLE_WORKFLOW, strict=False)
        assert isinstance(result, ValidationResult)
        assert result.is_valid

        # Should raise
        with pytest.raises(WorkflowValidationError):
            await validate_workflow_async({"invalid": "workflow"}, strict=True)

    def test_validate_workflow_schema(self) -> None:
        """Test the validate_workflow_schema function."""
        # Valid schema
        assert validate_workflow_schema(SAMPLE_WORKFLOW) is True

        # Invalid schema - should raise
        with pytest.raises(WorkflowValidationError):
            validate_workflow_schema({"invalid": "workflow"})

    @pytest.mark.asyncio  # type: ignore[misc]
    @async_test
    async def test_validate_workflow_schema_async(self) -> None:
        """Test the async validate_workflow_schema_async function."""
        # Valid schema
        assert await validate_workflow_schema_async(SAMPLE_WORKFLOW) is True

        # Invalid schema - should raise
        with pytest.raises(WorkflowValidationError):
            await validate_workflow_schema_async({"invalid": "workflow"})

    def test_validation_levels(self) -> None:
        """Test different validation levels."""
        # Create a workflow with various issues
        workflow: dict[str, Any] = {
            "version": "1.0.0",
            "name": "test_workflow",
            "description": "A test workflow",
            "tasks": {
                "task1": {
                    "type": "test",
                    "description": "Test task",
                    "action": "test_action",
                    "dependencies": ["nonexistent"],
                    "on_success": [{"next": "end"}],
                    "on_failure": [{"next": "end"}],
                }
            },
        }

        # Test schema-only validation
        schema_result = validate_workflow(
            workflow, level=ValidationLevel.SCHEMA_ONLY, strict=False
        )
        if isinstance(schema_result, bool):
            assert schema_result is True
        else:
            assert schema_result.is_valid

        # Test basic validation (should fail due to undefined reference)
        basic_result = validate_workflow(
            workflow, level=ValidationLevel.BASIC, strict=False
        )
        if isinstance(basic_result, bool):
            assert basic_result is False
        else:
            assert not basic_result.is_valid
            assert any("undefined task" in str(e) for e in basic_result.get_errors())
