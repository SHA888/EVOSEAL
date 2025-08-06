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


# We'll apply asyncio marks selectively to async tests

# Sample valid workflow for testing
SAMPLE_WORKFLOW: JSONObject = {
    "version": "1.0.0",
    "name": "test_workflow",
    "description": "A test workflow",
    "tasks": {
        "task1": {
            "type": "test",
            "description": "First task",
            "parameters": {"action": "test_action", "inputs": {"param1": "value1"}},
            "on_success": [{"next": "task2"}],
        },
        "task2": {
            "type": "test",
            "description": "Second task",
            "parameters": {"action": "another_action"},
            "dependencies": ["task1"],
            "on_success": [{"next": "task3"}],
        },
        "task3": {
            "type": "test",
            "description": "Final task",
            "parameters": {"action": "final_action"},
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
            "description": "First task",
            "parameters": {"action": "test_action"},
            "on_success": [{"next": "task2"}],
            "dependencies": ["task3"],
        },
        "task2": {
            "type": "test",
            "description": "Second task",
            "parameters": {"action": "another_action"},
            "on_success": [{"next": "task3"}],
            "dependencies": ["task1"],
        },
        "task3": {
            "type": "test",
            "description": "Final task",
            "parameters": {"action": "final_action"},
            "on_success": [{"next": "task1"}],
            "dependencies": ["task2"],
        },
    },
}


@pytest.fixture
def validator() -> WorkflowValidator:
    """Create a WorkflowValidator instance for testing."""
    return WorkflowValidator()


@pytest.fixture
def valid_workflow() -> dict[str, Any]:
    """Create a valid workflow dictionary for testing."""
    return {
        "name": "test_workflow",
        "version": "1.0.0",
        "tasks": {
            "task1": {
                "type": "python",
                "action": {
                    "module": "test_module",
                    "function": "test_function",
                },
                "next": "task2",
            },
            "task2": {
                "type": "python",
                "action": {
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
            }
        }
        # Add assertions here to validate the workflow
        assert workflow is not None


class TestWorkflowValidator:
    """Test cases for the WorkflowValidator class."""

    def test_validate_workflow(self, validator: WorkflowValidator, valid_workflow: dict[str, Any]) -> None:
        """Test workflow validation with a valid workflow."""
        result = validator.validate(valid_workflow)
        if not result.is_valid:
            print("\nValidation Errors:")
            for issue in result.issues:
                print(f"- {issue.message} (code: {issue.code})")
        assert result.is_valid
        assert not result.issues

    def test_validate_workflow_invalid(self, validator: WorkflowValidator, valid_workflow: dict[str, Any]) -> None:
        """Test workflow validation with an invalid workflow."""
        invalid_workflow = valid_workflow.copy()
        del invalid_workflow["name"]  # Make it invalid by removing required field
        
        result = validator.validate(invalid_workflow)
        assert not result.is_valid
        assert result.issues
        assert any("name" in str(issue) for issue in result.issues)

        # Test with different validation levels
        result = validator.validate(invalid_workflow, level=ValidationLevel.SCHEMA_ONLY)
        assert not result.is_valid

    def test_validate_invalid_schema(self, validator: WorkflowValidator) -> None:
        """Test validation of a workflow with an invalid schema."""
        invalid: dict[str, Any] = {"version": "1.0"}  # Missing required fields
        result = validator.validate(invalid)
        assert not result.is_valid
        assert result.issues
        assert any("required" in str(issue) for issue in result.issues)

        # Test with different validation levels
        result = validator.validate(invalid, level=ValidationLevel.SCHEMA_ONLY)
        assert not result.is_valid

    def test_validate_circular_dependency(self, validator: WorkflowValidator) -> None:
        """Test detection of circular dependencies."""
        workflow: JSONObject = INVALID_WORKFLOW  # Contains circular dependencies

        # Should pass with schema-only validation
        result = validator.validate(workflow, level=ValidationLevel.SCHEMA_ONLY)
        assert result.is_valid

        # Should fail with basic or full validation
        result = validator.validate(workflow, level=ValidationLevel.BASIC)
        assert not result.is_valid
        assert any("circular" in str(issue).lower() for issue in result.issues)

        result = validator.validate(workflow, level=ValidationLevel.FULL)
        assert not result.is_valid
        assert any("circular" in str(issue).lower() for issue in result.issues)

    def test_validate_undefined_task_reference(self, validator: WorkflowValidator) -> None:
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
        result = validator.validate(workflow, level=ValidationLevel.FULL)
        assert not result.is_valid
        assert any("nonexistent" in str(issue) for issue in result.issues)

        # Should pass with SCHEMA_ONLY validation
        result = validator.validate(workflow, level=ValidationLevel.SCHEMA_ONLY)
        assert result.is_valid

    def test_validate_partial(self, validator: WorkflowValidator, valid_workflow: dict[str, Any]) -> None:
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
        # With partial=True, should still fail schema validation
        result = validator.validate(workflow, level=ValidationLevel.FULL, partial=True)
        assert not result.is_valid

        # With SCHEMA_ONLY level, should pass
        result = validator.validate(workflow, level=ValidationLevel.SCHEMA_ONLY, partial=True)
        assert result.is_valid

    @async_test
    async def test_validate_async(self, validator: WorkflowValidator, valid_workflow: dict[str, Any]) -> None:
        """Test async validation."""
        result = await validator.validate_async(valid_workflow)
        assert result.is_valid
        assert not result.issues

    def test_register_custom_validator(self, validator: WorkflowValidator) -> None:
        """Test registering a custom validator."""

        def custom_validator(workflow: dict[str, Any], result: ValidationResult) -> None:
            if workflow.get("name") == "invalid":
                result.add_error("Invalid workflow name", code="invalid_name")

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

    def test_validate_workflow_non_strict(self, valid_workflow: dict[str, Any]) -> None:
        """Test the validate_workflow function in non-strict mode."""
        # Create a workflow with extra fields that would be invalid in strict mode
        workflow = valid_workflow.copy()
        workflow["extra_field"] = "should be allowed in non-strict mode"
        
        # Enable debug output
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        
        logger.debug("Original workflow: %s", workflow)
        
        # First validate in strict mode (should fail due to extra field)
        with pytest.raises(WorkflowValidationError) as exc_info:
            validate_workflow(workflow, strict=True)
        logger.debug("Strict validation failed as expected: %s", str(exc_info.value))
        
        # Now test non-strict mode
        result = validate_workflow(workflow, strict=False)
        
        # Print detailed validation errors if any
        if not result.is_valid:
            logger.error("\nValidation failed with errors:")
            for i, issue in enumerate(result.issues, 1):
                logger.error("%d. %s (code: %s, path: %s, exception: %s)", 
                           i, issue.message, issue.code, getattr(issue, 'path', 'N/A'), 
                           str(issue.exception) if hasattr(issue, 'exception') else 'None')
        
        # Debug: Print the schema being used
        from evoseal.utils.validator import _get_non_strict_validator
        validator = _get_non_strict_validator()
        logger.debug("Schema additionalProperties: %s", 
                    validator.schema.get('additionalProperties', 'Not set'))
        
        assert result.is_valid, f"Validation failed with {len(result.issues)} issues"
        assert not result.issues, f"Expected no validation issues, but got {len(result.issues)}"

        result = validate_workflow({"invalid": "workflow"}, strict=False)
        assert isinstance(result, ValidationResult)
        assert not result.is_valid

    @async_test
    async def test_validate_workflow_async(self) -> None:
        """Test the async validate_workflow_async function."""
        # Should not raise
        result = await validate_workflow_async(SAMPLE_WORKFLOW, strict=False)
        if isinstance(result, ValidationResult):
            assert result.is_valid
        else:
            assert result is True

        # Should raise
        with pytest.raises(WorkflowValidationError):
            await validate_workflow_async({"invalid": "workflow"}, strict=True)

    def test_validate_workflow_schema(self) -> None:
        """Test the validate_workflow_schema function."""
        # First, validate without raising to see the errors
        validator = WorkflowValidator()
        result = ValidationResult()
        workflow = validator._parse_workflow_definition(SAMPLE_WORKFLOW)
        is_valid = validator._validate_schema(workflow, result)

        # Print validation errors if any
        if not is_valid:
            print("\nSchema Validation Errors:")
            for issue in result.issues:
                print(f"- {issue.message} (code: {issue.code})")

        # Now test with the actual function
        assert validate_workflow_schema(SAMPLE_WORKFLOW) is True

        with pytest.raises(WorkflowValidationError):
            validate_workflow_schema({"invalid": "workflow"})

    @async_test
    async def test_validate_workflow_schema_async(self) -> None:
        """Test the async validate_workflow_schema_async function."""
        # Valid schema
        result = await validate_workflow_schema_async(SAMPLE_WORKFLOW)
        # Handle both boolean and ValidationResult returns
        if hasattr(result, "is_valid"):
            # It's a ValidationResult object
            assert result.is_valid
        else:
            # It should be a boolean
            assert result is True

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
        schema_result = validate_workflow(workflow, level=ValidationLevel.SCHEMA_ONLY, strict=False)
        if isinstance(schema_result, bool):
            assert schema_result is True
        else:
            assert schema_result.is_valid

        # Test basic validation (should fail due to undefined reference)
        basic_result = validate_workflow(workflow, level=ValidationLevel.BASIC, strict=False)
        if isinstance(basic_result, bool):
            assert basic_result is False
        else:
            assert not basic_result.is_valid
            assert any("undefined task" in str(e) for e in basic_result.get_errors())
