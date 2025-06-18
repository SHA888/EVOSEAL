"""Unit tests for the enhanced workflow validator."""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, List
import pytest

from evoseal.utils.validator import (
    WorkflowValidator,
    ValidationResult,
    ValidationLevel,
    WorkflowValidationError,
    validate_workflow,
    validate_workflow_async,
    validate_workflow_schema,
    validate_workflow_schema_async,
)

# Only mark async tests with asyncio
pytestmark = pytest.mark.asyncio(scope="function")

# Sample valid workflow for testing
SAMPLE_WORKFLOW = {
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
INVALID_WORKFLOW = {
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

    def test_validate_valid_workflow(self):
        """Test validating a valid workflow."""
        validator = WorkflowValidator()
        result = validator.validate(SAMPLE_WORKFLOW)
        assert result.is_valid
        assert not result.get_errors()

    def test_validate_invalid_schema(self):
        """Test validating a workflow with an invalid schema."""
        validator = WorkflowValidator()
        invalid = {"version": "1.0"}  # Missing required fields
        result = validator.validate(invalid)
        assert not result.is_valid
        assert any("required" in str(e) for e in result.get_errors())
        
        # Test with different validation levels
        result = validator.validate(invalid, level=ValidationLevel.SCHEMA_ONLY)
        assert not result.is_valid

    def test_validate_circular_dependency(self):
        """Test detecting circular dependencies."""
        validator = WorkflowValidator()
        result = validator.validate(INVALID_WORKFLOW, level=ValidationLevel.FULL)
        assert not result.is_valid
        assert any("circular" in str(e).lower() for e in result.get_errors())
        
        # Should still fail with BASIC level
        result = validator.validate(INVALID_WORKFLOW, level=ValidationLevel.BASIC)
        assert not result.is_valid
        
        # Should pass with SCHEMA_ONLY level (circular deps are semantic check)
        result = validator.validate(INVALID_WORKFLOW, level=ValidationLevel.SCHEMA_ONLY)
        assert result.is_valid

    def test_validate_undefined_task_reference(self):
        """Test detecting undefined task references."""
        workflow = {
            "version": "1.0.0",  # Must match the semantic versioning pattern in schema
            "name": "test",
            "tasks": {
                "task1": {
                    "type": "task",
                    "action": "test", 
                    "on_success": [{"next": "nonexistent"}]
                }
            },
        }
        validator = WorkflowValidator()
        
        # Should fail with FULL validation
        result = validator.validate(workflow, level=ValidationLevel.FULL)
        print(f"Validation result errors: {result.get_errors()}")
        print(f"Validation result is_valid: {result.is_valid}")
        assert not result.is_valid
        assert any("undefined" in str(e).lower() for e in result.get_errors())
        
        # Should pass with SCHEMA_ONLY validation
        result = validator.validate(workflow, level=ValidationLevel.SCHEMA_ONLY)
        assert result.is_valid

    def test_validate_partial(self):
        """Test partial validation skips some checks."""
        # This workflow has an undefined task reference but we're doing partial validation
        workflow = {
            "version": "1.0.0",  # Must match the semantic versioning pattern in schema
            "name": "test",
            "tasks": {
                "task1": {
                    "type": "task",
                    "action": "test", 
                    "on_success": [{"next": "nonexistent"}]}
            },
        }
        validator = WorkflowValidator()
        
        # With partial=True, should still fail schema validation
        result = validator.validate(workflow, level=ValidationLevel.FULL, partial=True)
        assert not result.is_valid
        
        # With SCHEMA_ONLY level, should pass
        result = validator.validate(workflow, level=ValidationLevel.SCHEMA_ONLY, partial=True)
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_validate_async(self):
        """Test async validation."""
        validator = WorkflowValidator()
        result = await validator.validate_async(SAMPLE_WORKFLOW)
        assert result.is_valid

    def test_register_custom_validator(self):
        """Test registering a custom validator."""
        def custom_validator(workflow: Dict[str, Any], result: ValidationResult):
            if workflow.get("name") == "invalid":
                result.add_error("Invalid workflow name", code="invalid_name")

        validator = WorkflowValidator()
        validator.register_validator(custom_validator)
        
        # Should pass custom validation
        result = validator.validate(SAMPLE_WORKFLOW)
        assert result.is_valid
        
        # Should fail custom validation
        invalid = SAMPLE_WORKFLOW.copy()
        invalid["name"] = "invalid"
        result = validator.validate(invalid)
        assert not result.is_valid
        assert any(e.get("code") == "invalid_name" for e in result.get_errors())


class TestConvenienceFunctions:
    """Test the convenience functions."""

    def test_validate_workflow_strict(self):
        """Test the validate_workflow function in strict mode."""
        # Should not raise
        assert validate_workflow(SAMPLE_WORKFLOW) is True
        
        # Should raise
        with pytest.raises(WorkflowValidationError):
            validate_workflow({"invalid": "workflow"})

    def test_validate_workflow_non_strict(self):
        """Test the validate_workflow function in non-strict mode."""
        result = validate_workflow(SAMPLE_WORKFLOW, strict=False)
        assert isinstance(result, ValidationResult)
        assert result.is_valid
        
        result = validate_workflow({"invalid": "workflow"}, strict=False)
        assert isinstance(result, ValidationResult)
        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_validate_workflow_async(self):
        """Test the async validate_workflow_async function."""
        # Should not raise
        assert await validate_workflow_async(SAMPLE_WORKFLOW) is True
        
        # Should raise
        with pytest.raises(WorkflowValidationError):
            await validate_workflow_async({"invalid": "workflow"})

    def test_validate_workflow_schema(self):
        """Test the validate_workflow_schema function."""
        # Valid schema
        assert validate_workflow_schema(SAMPLE_WORKFLOW) is True
        
        # Invalid schema - should raise
        with pytest.raises(WorkflowValidationError):
            validate_workflow_schema({"invalid": "workflow"})

    @pytest.mark.asyncio
    async def test_validate_workflow_schema_async(self):
        """Test the async validate_workflow_schema_async function."""
        # Valid schema
        assert await validate_workflow_schema_async(SAMPLE_WORKFLOW) is True
        
        # Invalid schema - should raise
        with pytest.raises(WorkflowValidationError):
            await validate_workflow_schema_async({"invalid": "workflow"})

    def test_validation_levels(self):
        """Test different validation levels."""
        # Schema-only should pass even with invalid references
        workflow = {
            "version": "1.0",
            "name": "test",
            "tasks": {"task1": {"action": "test", "on_success": [{"next": "nonexistent"}]}}
        }
        
        # Should pass schema validation
        result = validate_workflow(workflow, level="schema_only", strict=False)
        assert result.is_valid
        
        # Should fail with full validation
        result = validate_workflow(workflow, level="full", strict=False)
        assert not result.is_valid
        assert any("undefined" in str(e).lower() for e in result.get_errors())
