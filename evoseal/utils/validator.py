"""
Workflow Definition Validator

This module provides comprehensive validation for workflow definitions, including:
- JSON Schema validation
- Semantic validation
- Asynchronous validation
- Partial validation support
- Detailed error reporting
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable, TypeVar, Type, cast

import jsonschema
from jsonschema import Draft7Validator, ValidationError

# Get the directory containing this file
SCHEMA_DIR = Path(__file__).parent.parent / "schemas"
WORKFLOW_SCHEMA_PATH = SCHEMA_DIR / "workflow_schema.json"

# Type variable for generic validation result
T = TypeVar('T')

class ValidationLevel(Enum):
    """Validation level for workflow validation."""
    SCHEMA_ONLY = auto()  # Only validate against JSON schema
    BASIC = auto()       # Basic semantic validation
    FULL = auto()        # Full validation including deep checks

@dataclass
class ValidationIssue:
    """Represents a validation issue with details."""
    message: str
    path: str = ""
    severity: str = "error"  # 'error', 'warning', or 'info'
    code: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the issue to a dictionary."""
        return {
            'message': self.message,
            'path': self.path,
            'severity': self.severity,
            'code': self.code,
            'context': self.context
        }

class ValidationResult:
    """Container for validation results."""
    
    def __init__(self):
        self.issues: List[ValidationIssue] = []
        self._valid = True
    
    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a validation issue."""
        self.issues.append(issue)
        if issue.severity == 'error':
            self._valid = False
    
    def add_error(self, message: str, path: str = "", **kwargs: Any) -> None:
        """Add an error issue."""
        # Handle exception parameter by moving it to context
        exception = kwargs.pop('exception', None)
        context = kwargs.pop('context', {})
        if exception is not None:
            context['exception'] = str(exception)
        
        self.add_issue(ValidationIssue(
            message=message,
            path=path,
            severity='error',
            context=context,
            **kwargs
        ))
    
    def add_warning(self, message: str, path: str = "", **kwargs: Any) -> None:
        """Add a warning issue."""
        # Handle exception parameter by moving it to context
        exception = kwargs.pop('exception', None)
        context = kwargs.pop('context', {})
        if exception is not None:
            context['exception'] = str(exception)
            
        self.add_issue(ValidationIssue(
            message=message,
            path=path,
            severity='warning',
            context=context,
            **kwargs
        ))
    
    def add_info(self, message: str, path: str = "", **kwargs: Any) -> None:
        """Add an info issue."""
        # Handle exception parameter by moving it to context
        exception = kwargs.pop('exception', None)
        context = kwargs.pop('context', {})
        if exception is not None:
            context['exception'] = str(exception)
            
        self.add_issue(ValidationIssue(
            message=message,
            path=path,
            severity='info',
            context=context,
            **kwargs
        ))
    
    @property
    def is_valid(self) -> bool:
        """Return True if there are no errors."""
        return self._valid
    
    def get_errors(self) -> List[Dict[str, Any]]:
        """Get all error issues as dictionaries."""
        return [i.to_dict() for i in self.issues if i.severity == 'error']
    
    def get_warnings(self) -> List[Dict[str, Any]]:
        """Get all warning issues as dictionaries."""
        return [i.to_dict() for i in self.issues if i.severity == 'warning']
    
    def get_infos(self) -> List[Dict[str, Any]]:
        """Get all info issues as dictionaries."""
        return [i.to_dict() for i in self.issues if i.severity == 'info']
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary."""
        return {
            'valid': self.is_valid,
            'errors': self.get_errors(),
            'warnings': self.get_warnings(),
            'infos': self.get_infos()
        }

class WorkflowValidationError(ValueError):
    """Raised when a workflow fails validation."""
    
    def __init__(self, message: str, validation_result: Optional['ValidationResult'] = None, **kwargs):
        self.message = message
        self.validation_result = validation_result or ValidationResult()
        # Handle the case where 'errors' is passed instead of 'validation_result' for backward compatibility
        if 'errors' in kwargs and not self.validation_result.issues:
            for error in kwargs['errors']:
                self.validation_result.add_error(
                    error.get('message', 'Unknown error'),
                    code=error.get('code', 'unknown_error'),
                    path=error.get('path')
                )
        super().__init__(self.message)
        
    def __str__(self) -> str:
        if self.validation_result and self.validation_result.issues:
            error_details = "\n".join(
                f"- {issue.message} (code: {issue.code or 'no_code'})"
                for issue in self.validation_result.issues
            )
            return f"{self.message}\n{error_details}"
        return self.message

class WorkflowValidator:
    """Validates workflow definitions against the schema and business rules."""

    def __init__(self, schema_path: Optional[Union[str, Path]] = None):
        """Initialize the validator with the schema.

        Args:
            schema_path: Optional path to a custom schema file.
                        If not provided, uses the default schema.
        """
        self.schema_path = Path(schema_path) if schema_path else WORKFLOW_SCHEMA_PATH
        self.schema = self._load_schema()
        self.validator = Draft7Validator(self.schema)
        self._validators: List[Callable[[Dict[str, Any], ValidationResult], None]] = []
    
    def register_validator(self, validator: Callable[[Dict[str, Any], ValidationResult], None]) -> None:
        """Register a custom validator function.
        
        Args:
            validator: A function that takes a workflow dictionary and a ValidationResult,
                     and adds any validation issues to the result.
        """
        self._validators.append(validator)
    
    def _load_schema(self) -> Dict[str, Any]:
        """Load the JSON schema from file.

        Returns:
            The loaded schema as a dictionary.

        Raises:
            FileNotFoundError: If the schema file doesn't exist.
            json.JSONDecodeError: If the schema file contains invalid JSON.
        """
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

        with open(self.schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    def _parse_workflow(self, workflow_definition: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
        """Parse a workflow definition from various input types."""
        if isinstance(workflow_definition, dict):
            return workflow_definition
            
        if isinstance(workflow_definition, str):
            # Check if it's a JSON string
            if workflow_definition.strip().startswith('{') or workflow_definition.strip().startswith('['):
                return json.loads(workflow_definition)
            # Otherwise treat as file path
            path = Path(workflow_definition)
        else:
            path = Path(workflow_definition)
            
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")
            
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    def validate(
        self,
        workflow_definition: Union[Dict[str, Any], str, Path],
        level: Union[ValidationLevel, str] = ValidationLevel.FULL,
        partial: bool = False,
    ) -> ValidationResult:
        """Validate a workflow definition.
        
        Args:
            workflow_definition: The workflow definition to validate. Can be a dict,
                JSON string, or file path.
            level: The validation level to use. Can be 'schema_only', 'basic', or 'full'.
            partial: If True, skip some validations that aren't needed during editing.
                
        Returns:
            A ValidationResult object containing any validation errors.
            
        Raises:
            FileNotFoundError: If workflow_definition is a path that doesn't exist.
            json.JSONDecodeError: If workflow_definition is an invalid JSON string.
            ValueError: If an invalid validation level is provided.
        """
        # Parse the workflow definition if it's a string or path
        workflow = self._parse_workflow(workflow_definition)
        
        # Convert string level to enum if needed
        if isinstance(level, str):
            try:
                level = ValidationLevel[level.upper()]
            except KeyError as e:
                raise ValueError(
                    f"Invalid validation level: {level}. "
                    f"Must be one of: {', '.join(l.name.lower() for l in ValidationLevel)}"
                ) from e
        
        # Initialize validation result
        result = ValidationResult()
        
        try:
            # Always validate against schema first
            self.validator.validate(workflow)
        except ValidationError as e:
            path = "." + ".".join(str(p) for p in e.absolute_path) if e.absolute_path else ""
            result.add_error(
                f"Schema validation error: {e.message}",
                path=path,
                code="schema_validation_error",
                context={"validator": e.validator, "value": e.instance}
            )
            return result
            
        # If schema validation passed and we're in schema_only mode, return early
        if level == ValidationLevel.SCHEMA_ONLY:
            return result
            
        # Perform semantic validation based on level
        self._validate_semantics(workflow, result, level, partial)
        
        return result
    
    def _validate_semantics(
        self, 
        workflow: Dict[str, Any], 
        result: ValidationResult,
        level: ValidationLevel = ValidationLevel.FULL,
        partial: bool = False
    ) -> None:
        """Perform semantic validation of the workflow.
        
        This includes checks that can't be expressed in JSON schema.
        
        Args:
            workflow: The parsed workflow definition.
            result: The validation result to populate.
            level: The validation level to use.
            partial: If True, skip some validations that aren't needed during editing.
        """
        # Get all task names for reference checking
        task_names = set(workflow.get('tasks', {}).keys())

        # For SCHEMA_ONLY level, skip all semantic validation
        if level == ValidationLevel.SCHEMA_ONLY:
            return

        # Check for undefined task references (unless in partial mode)
        if not partial:
            self._check_undefined_references(workflow, task_names, result)

        # Check for circular dependencies (always check these as they can cause infinite loops)
        self._check_circular_dependencies(workflow, result)

        # For BASIC level, skip custom validators
        if level == ValidationLevel.BASIC:
            return

        # Run custom validators for FULL validation level
        for validator in self._validators:
            try:
                validator(workflow, result)
            except Exception as e:
                result.add_error(
                    f"Error in custom validator: {str(e)}",
                    code="validator_error",
                    exception=e
                )

    def _check_undefined_references(
        self, 
        workflow: Dict[str, Any], 
        task_names: Set[str], 
        result: ValidationResult
    ) -> None:
        """Check for undefined task references.
        
        Args:
            workflow: The workflow definition to check.
            task_names: Set of valid task names in the workflow.
            result: ValidationResult to add any issues to.
        """
        if not isinstance(workflow, dict):
            return
            
        tasks = workflow.get('tasks', {})
        if not isinstance(tasks, dict):
            return
            
        for task_name, task_def in tasks.items():
            if not isinstance(task_def, dict):
                continue
                
            # Check task dependencies
            dependencies = task_def.get('dependencies', [])
            if isinstance(dependencies, list):
                for i, dep in enumerate(dependencies):
                    if isinstance(dep, str) and dep not in task_names:
                        result.add_error(
                            f"Task '{task_name}' depends on undefined task '{dep}'",
                            path=f"tasks.{task_name}.dependencies[{i}]",
                            code="undefined_dependency"
                        )
            
            # Check on_success/on_failure actions
            for event_type in ['on_success', 'on_failure']:
                if event_type in task_def:
                    actions = task_def[event_type]
                    if not isinstance(actions, list):
                        result.add_error(
                            f"{event_type} in task '{task_name}' must be a list of actions",
                            path=f"tasks.{task_name}.{event_type}",
                            code="invalid_action_format"
                        )
                        continue
                        
                    for i, action in enumerate(actions):
                        if not isinstance(action, dict):
                            result.add_error(
                                f"Action at index {i} in {event_type} of task '{task_name}' must be an object",
                                path=f"tasks.{task_name}.{event_type}[{i}]",
                                code="invalid_action_format"
                            )
                            continue
                            
                        if 'next' in action and isinstance(action['next'], str) and action['next'] not in task_names:
                            result.add_error(
                                f"{event_type} in task '{task_name}' references undefined task '{action['next']}'",
                                path=f"tasks.{task_name}.{event_type}[{i}].next",
                                code="undefined_task_reference"
                            )
    
    def _check_circular_dependencies(self, workflow: Dict[str, Any], result: ValidationResult) -> None:
        """Check for circular dependencies."""
        tasks = workflow.get('tasks', {})
        cycles = self._check_cycles(tasks)
        if cycles:
            for cycle in cycles:
                result.add_error(
                    f"Circular dependency detected: {' -> '.join(cycle)}",
                    path="tasks",
                    code="circular_dependency"
                )
    
    def _check_cycles(self, tasks: Dict[str, Any]) -> List[List[str]]:
        """Check for cycles in task dependencies using depth-first search.
        
        Returns:
            List of cycles found, where each cycle is a list of task names.
        """
        visited = set()
        path = []
        cycles = []
        
        def has_cycle(task_name: str) -> bool:
            if task_name in path:
                # Found a cycle, record it
                cycle_start = path.index(task_name)
                cycles.append(path[cycle_start:] + [task_name])
                return True
                
            if task_name in visited:
                return False
                
            # Mark as visited and add to current path
            visited.add(task_name)
            path.append(task_name)
            
            # Check all dependencies of the current task
            task = tasks.get(task_name, {})
            for dep in task.get('dependencies', []):
                has_cycle(dep)
            
            # Backtrack
            path.pop()
            return False
        
        # Check for cycles starting from each task
        for task_name in tasks:
            if task_name not in visited:
                has_cycle(task_name)
                
        return cycles
    
    def _validate_semantics(
        self, 
        workflow: Dict[str, Any], 
        result: ValidationResult,
        level: ValidationLevel = ValidationLevel.FULL,
        partial: bool = False
    ) -> None:
        """Perform semantic validation of the workflow.
        
        This includes checks that can't be expressed in JSON schema.
        
        Args:
            workflow: The parsed workflow definition.
            result: The validation result to populate.
            level: The validation level to use.
            partial: If True, skip some validations that aren't needed during editing.
        """
        if not isinstance(workflow, dict):
            return
            
        # Get all task names for reference checking
        tasks = workflow.get('tasks', {})
        if not isinstance(tasks, dict):
            return
            
        task_names = set(tasks.keys())

        # For SCHEMA_ONLY level, skip all semantic validation
        if level == ValidationLevel.SCHEMA_ONLY:
            return

        # Check for undefined task references (unless in partial mode)
        if not partial and level in [ValidationLevel.BASIC, ValidationLevel.FULL]:
            self._check_undefined_references(workflow, task_names, result)

        # Check for circular dependencies (always check these as they can cause infinite loops)
        if level in [ValidationLevel.BASIC, ValidationLevel.FULL]:
            self._check_circular_dependencies(workflow, result)

        # For BASIC level, skip custom validators
        if level == ValidationLevel.BASIC:
            return

        # Run custom validators for FULL validation level
        for validator in self._validators:
            try:
                validator(workflow, result)
            except Exception as e:
                result.add_error(
                    f"Error in custom validator: {str(e)}",
                    code="validator_error",
                    exception=e
                )
        
    async def validate_async(
        self,
        workflow_definition: Union[Dict[str, Any], str, Path],
        level: ValidationLevel = ValidationLevel.FULL,
        partial: bool = False,
    ) -> ValidationResult:
        """Asynchronously validate a workflow definition.
        
        This is a wrapper around the synchronous validate method that runs it in a thread pool.
        
        Args:
            workflow_definition: The workflow definition to validate.
            level: The validation level to use.
            partial: If True, skip some validations that are only relevant for complete workflows.
            
        Returns:
            ValidationResult: The validation result.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.validate, workflow_definition, level, partial
        )
    
    def validate_strict(
        self,
        workflow_definition: Union[Dict[str, Any], str, Path],
        level: ValidationLevel = ValidationLevel.FULL,
        partial: bool = False,
    ) -> None:
        """Validate a workflow and raise an exception if invalid.
        
        Args:
            workflow_definition: The workflow definition to validate.
            level: The validation level to use.
            partial: If True, skip some validations that are only relevant for complete workflows.
            
        Raises:
            WorkflowValidationError: If the workflow is invalid.
        """
        result = self.validate(workflow_definition, level, partial)
        if not result.is_valid:
            raise WorkflowValidationError(
                "Workflow validation failed",
                validation_result=result
            )

def validate_workflow(
    workflow_definition: Union[Dict[str, Any], str, Path],
    level: Union[ValidationLevel, str] = ValidationLevel.FULL,
    partial: bool = False,
    strict: bool = True
) -> Union[bool, ValidationResult]:
    """Convenience function to validate a workflow definition.

    Args:
        workflow_definition: The workflow definition to validate.
                           Can be a dictionary, JSON string, or file path.
        level: The validation level to use. Can be a string ('schema_only', 'basic', 'full')
              or a ValidationLevel enum value.
        partial: If True, skip some validations that aren't needed during editing.
        strict: If True, raise an exception on validation errors. If False, return a ValidationResult.

    Returns:
        bool: True if the workflow is valid and strict=True.
        ValidationResult: If strict=False, returns the full validation result.

    Raises:
        WorkflowValidationError: If the workflow is invalid and strict=True.
        FileNotFoundError: If workflow_definition is a path that doesn't exist.
        json.JSONDecodeError: If workflow_definition is an invalid JSON string.
        ValueError: If an invalid validation level is provided.
    """
    # Convert string level to enum if needed
    if isinstance(level, str):
        try:
            level = ValidationLevel[level.upper()]
        except KeyError as e:
            raise ValueError(
                f"Invalid validation level: {level}. "
                f"Must be one of: {', '.join(l.name.lower() for l in ValidationLevel)}"
            ) from e
    
    validator = WorkflowValidator()
    
    if strict:
        validator.validate_strict(workflow_definition, level, partial)
        return True
    else:
        return validator.validate(workflow_definition, level, partial)


async def validate_workflow_async(
    workflow_definition: Union[Dict[str, Any], str, Path],
    level: Union[ValidationLevel, str] = ValidationLevel.FULL,
    partial: bool = False,
    strict: bool = True
) -> Union[bool, ValidationResult]:
    """Asynchronously validate a workflow definition.

    Args:
        workflow_definition: The workflow definition to validate.
                           Can be a dictionary, JSON string, or file path.
        level: The validation level to use. Can be a string ('schema_only', 'basic', 'full')
              or a ValidationLevel enum value.
        partial: If True, skip some validations that aren't needed during editing.
        strict: If True, raise an exception on validation errors. If False, return a ValidationResult.

    Returns:
        bool: True if the workflow is valid and strict=True.
        ValidationResult: If strict=False, returns the full validation result.

    Raises:
        WorkflowValidationError: If the workflow is invalid and strict=True.
        FileNotFoundError: If workflow_definition is a path that doesn't exist.
        json.JSONDecodeError: If workflow_definition is an invalid JSON string.
        ValueError: If an invalid validation level is provided.
    """
    # Convert string level to enum if needed
    if isinstance(level, str):
        try:
            level = ValidationLevel[level.upper()]
        except KeyError as e:
            raise ValueError(
                f"Invalid validation level: {level}. "
                f"Must be one of: {', '.join(l.name.lower() for l in ValidationLevel)}"
            ) from e
    
    validator = WorkflowValidator()
    
    if strict:
        await validator.validate_async(workflow_definition, level, partial)
        return True
    else:
        return await validator.validate_async(workflow_definition, level, partial)


def validate_workflow_schema(workflow_definition: Union[Dict[str, Any], str, Path]) -> bool:
    """Quickly validate a workflow against just the JSON schema.
    
    This is a convenience function for when you only need to check the schema.
    """
    return validate_workflow(workflow_definition, ValidationLevel.SCHEMA_ONLY)


async def validate_workflow_schema_async(workflow_definition: Union[Dict[str, Any], str, Path]) -> bool:
    """Quickly validate a workflow against just the JSON schema asynchronously.
    
    This is a convenience function for when you only need to check the schema.
    """
    return await validate_workflow_async(workflow_definition, ValidationLevel.SCHEMA_ONLY)
