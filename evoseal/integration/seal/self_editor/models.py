"""Data models for the SelfEditor component."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional


class EditOperation(str, Enum):
    """Types of edit operations that can be performed.

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


class EditCriteria(Enum):
    """Criteria used to evaluate and categorize edit suggestions."""

    STYLE = auto()
    PERFORMANCE = auto()
    SECURITY = auto()
    DOCUMENTATION = auto()
    READABILITY = auto()
    MAINTAINABILITY = auto()
    COMPLETENESS = auto()
    ACCURACY = auto()
    CLARITY = auto()
    CONSISTENCY = auto()
    ERROR_HANDLING = auto()


@dataclass
class EditSuggestion:
    """Represents a suggested edit to content.

    Attributes:
        operation: The type of edit operation to perform
        criteria: List of criteria that this suggestion addresses
        original_text: The original text to be modified (if any)
        suggested_text: The suggested replacement text (if any)
        explanation: Human-readable explanation of the suggestion
        confidence: Confidence level (0.0 to 1.0) in the suggestion
        line_number: Line number where the suggestion applies (1-based)
        metadata: Additional metadata about the suggestion
    """

    operation: EditOperation
    criteria: list[EditCriteria]
    original_text: str = ""
    suggested_text: str = ""
    explanation: str = ""
    confidence: float = 1.0
    line_number: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the suggestion after initialization."""
        if not self.explanation and self.operation != EditOperation.NOTE:
            self.explanation = f"Suggested {self.operation.name.lower()}"

        if self.confidence < 0 or self.confidence > 1:
            raise ValueError("Confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        """Convert the EditSuggestion to a dictionary.

        Returns:
            Dict containing the EditSuggestion data
        """
        return {
            "operation": self.operation.name.lower(),
            "criteria": [criterion.name.lower() for criterion in self.criteria],
            "original_text": self.original_text,
            "suggested_text": self.suggested_text,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "line_number": self.line_number,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditSuggestion":
        """Create an EditSuggestion from a dictionary.

        Args:
            data: Dictionary containing EditSuggestion data

        Returns:
            A new EditSuggestion instance
        """
        return cls(
            operation=EditOperation[data["operation"].upper()],
            criteria=[EditCriteria[crit.upper()] for crit in data.get("criteria", [])],
            original_text=data.get("original_text", ""),
            suggested_text=data.get("suggested_text", ""),
            explanation=data.get("explanation", ""),
            confidence=data.get("confidence", 1.0),
            line_number=data.get("line_number"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class EditHistoryEntry:
    """Represents an entry in the edit history.

    Attributes:
        timestamp: When the edit was made
        operation: Type of operation performed
        content_id: Identifier for the content being edited
        suggestion: The suggestion that was applied
        applied: Whether the suggestion was applied or rejected
        user: Identifier for the user who made the edit
    """

    timestamp: datetime
    operation: EditOperation
    content_id: str
    suggestion: EditSuggestion
    applied: bool
    user: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentState:
    """Represents the state of a piece of content being edited.

    Attributes:
        content_id: Unique identifier for the content
        original_content: The original content
        current_content: The current state of the content
        history: List of edit operations applied
        created_at: When the content was first created
        updated_at: When the content was last modified
        metadata: Additional metadata about the content
    """

    content_id: str
    original_content: str
    current_content: str
    history: list[EditHistoryEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_history_entry(self, entry: EditHistoryEntry) -> None:
        """Add an entry to the edit history.

        Args:
            entry: The edit history entry to add
        """
        self.history.append(entry)
        self.updated_at = datetime.utcnow()


@dataclass
class EditResult:
    """The result of applying an edit.

    Attributes:
        success: Whether the edit was successful
        content: The resulting content after the edit
        error: Any error that occurred
        suggestion: The suggestion that was applied
    """

    success: bool
    content: Optional[str] = None
    error: Optional[Exception] = None
    suggestion: Optional[EditSuggestion] = None

    @classmethod
    def create_success(cls, content: str, suggestion: EditSuggestion) -> "EditResult":
        """Create a successful edit result.

        Args:
            content: The resulting content after the edit
            suggestion: The suggestion that was applied

        Returns:
            A new EditResult instance with success=True
        """
        return cls(True, content=content, suggestion=suggestion)

    @classmethod
    def failure(cls, error: Exception, suggestion: EditSuggestion) -> "EditResult":
        """Create a failed edit result.

        Args:
            error: The error that occurred
            suggestion: The suggestion that was attempted

        Returns:
            A new EditResult instance with success=False
        """
        return cls(False, error=error, suggestion=suggestion)

    def __bool__(self) -> bool:
        """Convert the result to a boolean.

        Returns:
            bool: True if the edit was successful, False otherwise
        """
        return self.success
