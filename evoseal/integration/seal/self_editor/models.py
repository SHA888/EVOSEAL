"""Data models for the SelfEditor component."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, Dict, Any, Union


class EditOperation(Enum):
    """Types of edit operations that can be performed."""
    ADD = auto()
    REMOVE = auto()
    REWRITE = auto()
    MOVE = auto()
    NOTE = auto()


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
    criteria: List[EditCriteria]
    original_text: str = ""
    suggested_text: str = ""
    explanation: str = ""
    confidence: float = 1.0
    line_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the suggestion after initialization."""
        if not self.explanation and self.operation != EditOperation.NOTE:
            self.explanation = f"Suggested {self.operation.name.lower()}"
            
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError("Confidence must be between 0.0 and 1.0")


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
    metadata: Dict[str, Any] = field(default_factory=dict)


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
    history: List[EditHistoryEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_history_entry(self, entry: EditHistoryEntry):
        """Add an entry to the edit history."""
        self.history.append(entry)
        self.updated_at = datetime.utcnow()


class EditResult:
    """The result of applying an edit."""
    
    def __init__(self, 
                 success: bool,
                 content: Optional[str] = None,
                 error: Optional[Exception] = None,
                 suggestion: Optional[EditSuggestion] = None):
        """Initialize the edit result.
        
        Args:
            success: Whether the edit was successful
            content: The resulting content after the edit
            error: Any error that occurred
            suggestion: The suggestion that was applied
        """
        self.success = success
        self.content = content
        self.error = error
        self.suggestion = suggestion
    
    @classmethod
    def success(cls, content: str, suggestion: EditSuggestion) -> 'EditResult':
        """Create a successful edit result."""
        return cls(True, content=content, suggestion=suggestion)
    
    @classmethod
    def failure(cls, error: Exception, suggestion: EditSuggestion) -> 'EditResult':
        """Create a failed edit result."""
        return cls(False, error=error, suggestion=suggestion)
    
    def __bool__(self):
        return self.success
