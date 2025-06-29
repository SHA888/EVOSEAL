"""
SelfEditor module for the SEAL system.

This module provides the SelfEditor class that enables the system to review and improve its own outputs.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional, Protocol, TypeVar, Union

from pydantic import BaseModel, Field

# Set up logging
logger = logging.getLogger(__name__)


class EditOperation(str, Enum):
    """Types of edit operations that can be performed on content.

    - ADD: Add new content
    - REMOVE: Remove existing content
    - REPLACE: Replace existing content with new content
    - REWRITE: Completely rewrite the content
    - FORMAT: Reformat the content without changing its meaning
    - CLARIFY: Add clarification or documentation
    - MOVE: Move content to a different location
    - NOTE: Add a note without changing content
    """

    ADD = "add"
    REMOVE = "remove"
    REPLACE = "replace"
    REWRITE = "rewrite"
    FORMAT = "format"
    CLARIFY = "clarify"
    MOVE = "move"
    NOTE = "note"


class EditCriteria(str, Enum):
    """Criteria for evaluating content quality."""

    # Core quality attributes
    CLARITY = "clarity"
    CONCISENESS = "conciseness"
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    COMPLETENESS = "completeness"
    COHERENCE = "coherence"
    READABILITY = "readability"
    STYLE = "style"

    # Code quality specific
    DOCUMENTATION = "documentation"  # For documentation-related suggestions
    SECURITY = "security"  # For security-related suggestions
    ROBUSTNESS = "robustness"  # For code resilience and error handling
    BEST_PRACTICE = "best_practice"  # For following language/framework best practices
    ERROR_HANDLING = "error_handling"  # For proper error handling
    PERFORMANCE = "performance"  # For performance-related suggestions


class EditSuggestion(BaseModel):
    """Represents a suggested edit to a piece of content."""

    operation: EditOperation
    criteria: list[EditCriteria]
    original_text: str
    suggested_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert the suggestion to a dictionary."""
        return {
            "operation": self.operation.value,
            "criteria": [c.value for c in self.criteria],
            "original_text": self.original_text,
            "suggested_text": self.suggested_text,
            "confidence": self.confidence,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EditSuggestion:
        """Create an EditSuggestion from a dictionary."""
        return cls(
            operation=EditOperation(data["operation"]),
            criteria=[EditCriteria(c) for c in data["criteria"]],
            original_text=data["original_text"],
            suggested_text=data["suggested_text"],
            confidence=data.get("confidence", 0.5),
            explanation=data.get("explanation", ""),
        )


class EditHistory(BaseModel):
    """Tracks the history of edits made to a piece of content."""

    content_id: str
    original_content: str
    current_content: str
    edit_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def add_edit(self, suggestion: EditSuggestion, applied: bool = True) -> None:
        """Add an edit to the history."""
        self.edit_history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "suggestion": suggestion.to_dict(),
                "applied": applied,
                "content_before": self.current_content,
                "content_after": (suggestion.suggested_text if applied else self.current_content),
            }
        )
        self.current_content = suggestion.suggested_text if applied else self.current_content
        self.updated_at = datetime.now(timezone.utc)


class EditStrategy(Protocol):
    """Protocol for defining editing strategies."""

    def evaluate(self, content: str, **kwargs: Any) -> list[EditSuggestion]:
        """Evaluate content and return suggested edits."""
        ...

    def apply_edit(self, content: str, suggestion: EditSuggestion) -> str:
        """Apply a suggested edit to the content."""
        ...


class DefaultEditStrategy:
    """Default implementation of the EditStrategy protocol."""

    def __init__(self, criteria: list[EditCriteria] | None = None):
        self.criteria = criteria or [
            # Core quality criteria
            EditCriteria.CLARITY,
            EditCriteria.CONCISENESS,
            EditCriteria.ACCURACY,
            EditCriteria.RELEVANCE,
            EditCriteria.COMPLETENESS,
            # Code quality criteria
            EditCriteria.STYLE,
            EditCriteria.DOCUMENTATION,
            EditCriteria.SECURITY,
            EditCriteria.ROBUSTNESS,
            EditCriteria.BEST_PRACTICE,
            EditCriteria.ERROR_HANDLING,
            EditCriteria.PERFORMANCE,
        ]

    def evaluate(self, content: str, **kwargs: Any) -> list[EditSuggestion]:
        """Evaluate content and return suggested edits.

        This implementation provides basic code analysis and suggestions.
        In a production environment, this would integrate with more sophisticated
        static analysis tools and language models.
        """
        suggestions = []

        # Check for common Python style issues
        if "  " in content:  # Multiple spaces
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "  " in line.rstrip() and not line.strip().startswith("#"):
                    suggestions.append(
                        EditSuggestion(
                            operation=EditOperation.REWRITE,
                            criteria=[EditCriteria.STYLE],
                            original_text=line,
                            suggested_text=line.replace("  ", " "),
                            confidence=0.8,
                            explanation="Replace multiple spaces with a single space",
                        )
                    )

        # Check for long lines (over 88 characters, PEP 8 recommendation)
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if len(line) > 88 and not line.strip().startswith("#"):
                suggestions.append(
                    EditSuggestion(
                        operation=EditOperation.REWRITE,
                        criteria=[EditCriteria.STYLE, EditCriteria.READABILITY],
                        original_text=line,
                        suggested_text=line,  # Actual line wrapping would be done in apply_edit
                        confidence=0.7,
                        explanation=f"Line {i+1} exceeds 88 characters (PEP 8 recommendation)",
                    )
                )

        # Check for potential security issues
        security_keywords = [
            "subprocess.call(",
            "os.system(",
            "eval(",
            "exec(",
            "pickle.loads(",
            "yaml.load(",
            "json.loads(",
            "input(",
            "execfile(",
            "compile(",
        ]

        for keyword in security_keywords:
            if keyword in content:
                suggestions.append(
                    EditSuggestion(
                        operation=EditOperation.CLARIFY,
                        criteria=[EditCriteria.SECURITY],
                        original_text=content,
                        suggested_text=f"# SECURITY: {content}",
                        confidence=0.9,
                        explanation=f"Potential security issue detected: {keyword}",
                    )
                )

        return suggestions

    def _normalize_operation(self, operation: Any) -> EditOperation:
        """Normalize operation to ensure consistent comparison.

        Args:
            operation: The operation to normalize (can be string, enum, etc.)

        Returns:
            The normalized EditOperation enum value

        Raises:
            ValueError: If the operation cannot be normalized to a valid EditOperation
        """
        if isinstance(operation, EditOperation):
            return operation

        if isinstance(operation, str):
            try:
                return EditOperation(operation.lower())
            except ValueError as e:
                raise ValueError(f"Invalid operation: {operation}") from e

        raise TypeError(f"Unsupported operation type: {type(operation).__name__}")

    def _log_operation_start(self, op_name: str, content: str, suggestion: EditSuggestion) -> None:
        """Log operation start with relevant debug information."""
        if not logger.isEnabledFor(logging.DEBUG):
            return

        logger.debug(f"{op_name} - Operation: {suggestion.operation}")
        logger.debug(f"{op_name} - Original text: {suggestion.original_text!r}")
        logger.debug(f"{op_name} - Suggested text: {suggestion.suggested_text!r}")
        logger.debug(f"{op_name} - Content length: {len(content)}")

        if suggestion.original_text:
            logger.debug(
                f"{op_name} - Original text in content: " f"{suggestion.original_text in content}"
            )

    def _handle_rewrite(self, content: str, suggestion: EditSuggestion) -> str:
        """Handle REWRITE operation.

        For REWRITE operation, always return the suggested_text regardless of original_text.
        """
        self._log_operation_start("REWRITE", content, suggestion)
        # For REWRITE operation, always return the suggested_text
        return str(suggestion.suggested_text) if suggestion.suggested_text is not None else ""

    def _handle_add(self, content: str, suggestion: EditSuggestion) -> str:
        """Handle ADD operation."""
        self._log_operation_start("ADD", content, suggestion)

        if not suggestion.original_text:
            return f"{suggestion.suggested_text or ''}{content}"

        if suggestion.original_text in content:
            return content.replace(
                str(suggestion.original_text), str(suggestion.suggested_text or ""), 1
            )

        return content

    def _handle_remove(self, content: str, suggestion: EditSuggestion) -> str:
        """Handle REMOVE operation."""
        self._log_operation_start("REMOVE", content, suggestion)

        if not suggestion.original_text:
            logger.debug("REMOVE - No original text provided")
            return content

        original_text = str(suggestion.original_text)
        if original_text not in content:
            logger.debug("REMOVE - Text not found in content")
            return content

        result = content.replace(original_text, "", 1)
        logger.debug(f"REMOVE - Removed {len(original_text)} characters")
        return result

    def _handle_replace(self, content: str, suggestion: EditSuggestion) -> str:
        """Handle REPLACE operation."""
        self._log_operation_start("REPLACE", content, suggestion)

        if not suggestion.original_text or suggestion.original_text not in content:
            return content

        return content.replace(
            str(suggestion.original_text), str(suggestion.suggested_text or ""), 1
        )

    def _handle_format(self, content: str, suggestion: EditSuggestion) -> str:
        """Handle FORMAT operation."""
        self._log_operation_start("FORMAT", content, suggestion)
        return "\n".join(line.rstrip() for line in content.split("\n"))

    def _handle_clarify(self, content: str, suggestion: EditSuggestion) -> str:
        """Handle CLARIFY operation."""
        self._log_operation_start("CLARIFY", content, suggestion)
        explanation = suggestion.explanation or "No explanation provided"
        return f"# NOTE: {explanation}\n{content}"

    def apply_edit(self, content: str, suggestion: EditSuggestion) -> str:
        """Apply a suggested edit to the content.

        This implementation handles basic edit operations. More complex operations
        might require specialized tools or libraries.

        Args:
            content: The content to modify
            suggestion: The edit suggestion to apply

        Returns:
            The modified content after applying the edit

        Raises:
            ValueError: If the operation is invalid or unsupported
            TypeError: If the input types are incorrect
        """
        # Handle the case where this method is called directly as a class method
        # In that case, content is actually self and suggestion is content
        if isinstance(self, str) and isinstance(content, EditSuggestion):
            # Swap parameters
            actual_content: str = self
            actual_suggestion: EditSuggestion = content
        else:
            # Ensure content is a string if needed
            actual_content = str(content) if not isinstance(content, str) else content
            actual_suggestion = suggestion

        # For direct class method calls, we need to be careful with type checking
        # as the EditSuggestion import might be different
        if (
            not hasattr(actual_suggestion, "operation")
            or not hasattr(actual_suggestion, "original_text")
            or not hasattr(actual_suggestion, "suggested_text")
        ):
            raise TypeError(
                f"Expected EditSuggestion-like object, got {type(actual_suggestion).__name__}"
            )

        # Get the operation
        operation = actual_suggestion.operation
        if isinstance(operation, str):
            try:
                operation = EditOperation(operation.lower())
            except ValueError:
                # Try to handle the case where operation is a string but not a valid EditOperation value
                pass

        # Handle REWRITE operation - always return the suggested_text
        if str(operation) == str(EditOperation.REWRITE) or operation == EditOperation.REWRITE:
            return (
                str(actual_suggestion.suggested_text)
                if actual_suggestion.suggested_text is not None
                else ""
            )

        # Handle ADD operation
        if str(operation) == str(EditOperation.ADD) or operation == EditOperation.ADD:
            if not actual_suggestion.original_text:
                # Prepend suggested_text when original_text is empty
                return f"{actual_suggestion.suggested_text or ''}{actual_content}"

            # If original_text exists, replace it with suggested_text
            if actual_suggestion.original_text in actual_content:
                return actual_content.replace(
                    str(actual_suggestion.original_text),
                    str(actual_suggestion.suggested_text or ""),
                    1,
                )

            return actual_content

        # Handle REMOVE operation
        if str(operation) == str(EditOperation.REMOVE) or operation == EditOperation.REMOVE:
            if not actual_suggestion.original_text:
                return actual_content

            # Check if the original text is in the content
            if actual_suggestion.original_text not in actual_content:
                return actual_content

            # Remove the first occurrence of original_text
            return actual_content.replace(actual_suggestion.original_text, "", 1)

        # Handle REPLACE operation
        if str(operation) == str(EditOperation.REPLACE) or operation == EditOperation.REPLACE:
            if (
                not actual_suggestion.original_text
                or actual_suggestion.original_text not in actual_content
            ):
                return actual_content

            return actual_content.replace(
                str(actual_suggestion.original_text),
                str(actual_suggestion.suggested_text or ""),
                1,
            )

        # Handle FORMAT operation
        if str(operation) == str(EditOperation.FORMAT) or operation == EditOperation.FORMAT:
            return "\n".join(line.rstrip() for line in actual_content.split("\n"))

        # Handle CLARIFY operation
        if str(operation) == str(EditOperation.CLARIFY) or operation == EditOperation.CLARIFY:
            explanation = (
                actual_suggestion.explanation
                if hasattr(actual_suggestion, "explanation") and actual_suggestion.explanation
                else "No explanation provided"
            )
            return f"# NOTE: {explanation}\n{actual_content}"

        # Default case: return content unchanged
        return actual_content


class SelfEditor:
    """A class that enables the system to review and improve its own outputs.

    The SelfEditor provides functionality to:
    1. Define editing criteria and rules
    2. Evaluate generated content against these criteria
    3. Suggest or apply improvements to outputs
    4. Maintain an editing history for tracking changes
    5. Provide configurable editing strategies
    """

    def __init__(
        self,
        strategy: EditStrategy | None = None,
        auto_apply: bool = False,
        min_confidence: float = 0.7,
        history_limit: int = 100,
    ):
        """Initialize the SelfEditor.

        Args:
            strategy: The editing strategy to use. If None, a default strategy will be used.
            auto_apply: Whether to automatically apply suggested edits.
            min_confidence: Minimum confidence threshold for applying suggestions.
            history_limit: Maximum number of edit histories to keep in memory.
        """
        self.strategy = strategy or DefaultEditStrategy()
        self.auto_apply = auto_apply
        self.min_confidence = min_confidence
        self.history_limit = history_limit
        self.histories: dict[str, EditHistory] = {}

    def evaluate_content(
        self, content: str, content_id: str | None = None, **kwargs: Any
    ) -> list[EditSuggestion]:
        """Evaluate content and return suggested edits.

        Args:
            content: The content to evaluate.
            content_id: Optional identifier for the content. If provided, the edit history
                       will be tracked.
            **kwargs: Additional arguments to pass to the evaluation strategy.

        Returns:
            A list of suggested edits.
        """
        suggestions = self.strategy.evaluate(content, **kwargs)

        if content_id is not None:
            if content_id in self.histories:
                history = self.histories[content_id]
                history.original_content = content  # Update original content if needed
            else:
                history = EditHistory(
                    content_id=content_id,
                    original_content=content,
                    current_content=content,
                )
                self.histories[content_id] = history
                # Enforce history limit after adding a new history
                self._enforce_history_limit()

            # Apply auto-applicable suggestions
            if self.auto_apply:
                current_content = content
                for suggestion in suggestions:
                    if suggestion.confidence >= self.min_confidence:
                        self.histories[content_id].add_edit(suggestion, applied=True)
                        current_content = self.strategy.apply_edit(current_content, suggestion)

                # Update the current content in the history
                self.histories[content_id].current_content = current_content

                # Return only unapplied suggestions
                return [s for s in suggestions if s.confidence < self.min_confidence]

        return suggestions

    def apply_edit(self, content_id: str, suggestion: EditSuggestion, apply: bool = True) -> str:
        """Apply or reject an edit suggestion.

        Args:
            content_id: The ID of the content to edit.
            suggestion: The suggested edit to apply.
            apply: Whether to apply the edit. If False, the suggestion will be recorded
                  but not applied.

        Returns:
            The edited content if applied, or the original content if not.

        Raises:
            KeyError: If no content exists with the given ID.
        """
        if content_id not in self.histories:
            raise KeyError(f"No content found with ID: {content_id}")

        history = self.histories[content_id]
        history.add_edit(suggestion, applied=apply)

        if apply:
            history.current_content = self.strategy.apply_edit(history.current_content, suggestion)

        # Enforce history limit
        self._enforce_history_limit()

        return history.current_content

    def _enforce_history_limit(self) -> None:
        """Enforce the history limit by removing the oldest histories if needed."""
        while len(self.histories) > self.history_limit:
            # Remove the oldest history
            oldest_id = min(self.histories.keys(), key=lambda k: self.histories[k].updated_at)
            del self.histories[oldest_id]

    def get_edit_history(self, content_id: str) -> EditHistory | None:
        """Get the edit history for a piece of content.

        Args:
            content_id: The ID of the content.

        Returns:
            The edit history, or None if no content exists with the given ID.
        """
        return self.histories.get(content_id)

    def get_current_content(self, content_id: str) -> str | None:
        """Get the current version of a piece of content.

        Args:
            content_id: The ID of the content.

        Returns:
            The current content, or None if no content exists with the given ID.
        """
        return self.histories[content_id].current_content if content_id in self.histories else None

    def reset_content(self, content_id: str) -> str | None:
        """Reset content to its original state.

        Args:
            content_id: The ID of the content to reset.

        Returns:
            The original content, or None if no content exists with the given ID.
        """
        if content_id in self.histories:
            history = self.histories[content_id]
            history.current_content = history.original_content
            history.edit_history = []
            history.updated_at = datetime.now(timezone.utc)
            return history.current_content
        return None
