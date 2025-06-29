"""Type definitions for the workflow validator.

This module contains type definitions and base classes used by the workflow validator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Literal, Protocol, TypedDict, Union

from typing_extensions import TypeAlias

# Type aliases for JSON data structures
JSONPrimitive = Union[str, int, float, bool, None]
JSONArray = list["JSONValue"]
JSONObject = dict[str, "JSONValue"]
JSONValue = Union[JSONPrimitive, JSONArray, JSONObject]

# Type alias for validator functions
Validator: TypeAlias = Callable[[JSONObject, "ValidationResult"], None]


class _ValidationContext(TypedDict, total=False):
    """Internal type for validation context data."""

    validator: str
    value: Any
    exception: str
    cycle: list[str]


class ValidationContext(dict[str, Any]):
    """Type for validation context data with type-safe accessors."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def update(self, other: dict[str, Any] | None = None, **kwargs: Any) -> None:  # type: ignore[override]
        """Update the context with new values."""
        if other:
            super().update(other)
        if kwargs:
            super().update(kwargs)


class ValidationLevel(Enum):
    """Validation level for workflow validation."""

    SCHEMA_ONLY = auto()  # Only validate against JSON schema
    BASIC = auto()  # Basic validation including references
    FULL = auto()  # Full validation including deep checks


@dataclass
class ValidationIssue:
    """A single validation issue (error, warning, or info)."""

    message: str
    path: str = ""
    severity: Literal["error", "warning", "info"] = "error"
    code: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the issue to a dictionary."""
        result: dict[str, Any] = {
            "message": self.message,
            "severity": self.severity,
        }
        if self.path:
            result["path"] = self.path
        if self.code:
            result["code"] = self.code
        if self.context:
            result["context"] = dict(self.context)
        return result


class ValidationResult:
    """Container for validation results with type-safe methods."""

    def __init__(self) -> None:
        """Initialize a new ValidationResult with empty issues and valid state."""
        self.issues: list[ValidationIssue] = []
        self._valid = True
        self.data: dict[str, Any] = {}  # Changed from None to empty dict for consistency

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a validation issue.

        Args:
            issue: The validation issue to add.
        """
        self.issues.append(issue)
        if issue.severity == "error":
            self._valid = False

    def add_error(
        self,
        message: str,
        path: str = "",
        code: str = "",
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Add an error with the given message and path.

        Args:
            message: The error message.
            path: The path to the error in the workflow.
            code: An optional error code.
            context: Optional context data.
            **kwargs: Additional context data.
        """
        ctx = ValidationContext()
        if context:
            ctx.update(context)
        if kwargs:
            ctx.update(kwargs)
        self.add_issue(
            ValidationIssue(
                message=message,
                path=path,
                severity="error",
                code=code,
                context=ctx,
            )
        )

    def add_warning(
        self,
        message: str,
        path: str = "",
        code: str = "",
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Add a warning with the given message and path.

        Args:
            message: The warning message.
            path: The path to the warning in the workflow.
            code: An optional warning code.
            context: Optional context data.
            **kwargs: Additional context data.
        """
        ctx = ValidationContext()
        if context:
            ctx.update(context)
        if kwargs:
            ctx.update(kwargs)
        self.add_issue(
            ValidationIssue(
                message=message,
                path=path,
                severity="warning",
                code=code,
                context=ctx,
            )
        )

    def add_info(
        self,
        message: str,
        path: str = "",
        code: str = "",
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Add an info message with the given message and path.

        Args:
            message: The info message.
            path: The path to the info in the workflow.
            code: An optional info code.
            context: Optional context data.
            **kwargs: Additional context data.
        """
        ctx = ValidationContext()
        if context:
            ctx.update(context)
        if kwargs:
            ctx.update(kwargs)
        self.add_issue(
            ValidationIssue(
                message=message,
                path=path,
                severity="info",
                code=code,
                context=ctx,
            )
        )

    @property
    def is_valid(self) -> bool:
        """Return True if there are no errors."""
        return self._valid

    @is_valid.setter
    def is_valid(self, value: bool) -> None:
        """Set the validation status."""
        self._valid = value

    @property
    def errors(self) -> list[dict[str, Any]]:
        """Get all error issues as dictionaries."""
        return [issue.to_dict() for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[dict[str, Any]]:
        """Get all warning issues as dictionaries."""
        return [issue.to_dict() for issue in self.issues if issue.severity == "warning"]

    def get_errors(self) -> list[ValidationIssue]:
        """Get all error issues."""
        return [issue for issue in self.issues if issue.severity == "error"]

    def get_warnings(self) -> list[ValidationIssue]:
        """Get all warning issues."""
        return [issue for issue in self.issues if issue.severity == "warning"]

    def get_infos(self) -> list[ValidationIssue]:
        """Get all info issues."""
        return [issue for issue in self.issues if issue.severity == "info"]

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to a dictionary."""
        return {
            "valid": self.is_valid,
            "errors": [issue.to_dict() for issue in self.get_errors()],
            "warnings": [issue.to_dict() for issue in self.get_warnings()],
            "infos": [issue.to_dict() for issue in self.get_infos()],
        }


# Type aliases for better readability
# JSONValue is already defined at the top of the file
# JSONObject is already defined at the top of the file


class ValidatorFunction(Protocol):
    """Protocol for validator functions."""

    def __call__(self, workflow: JSONObject, result: ValidationResult) -> None: ...


# Validator type alias is already defined at the top of the file
