"""Common types and data structures used throughout the SEAL system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set, Union


class DataFormat(str, Enum):
    """Supported data formats for loading and saving data."""

    JSON = "json"
    YAML = "yaml"
    CSV = "csv"
    TXT = "txt"


@dataclass
class PromptTemplate:
    """A template for generating prompts with variables.

    Attributes:
        name: Unique identifier for the template
        template: The template string with {placeholders}
        description: Human-readable description of the template's purpose
        style: The style of the template (e.g., INSTRUCTION, CHAT)
        required_fields: Set of required template variables
        version: Optional version identifier
    """

    name: str
    template: str
    description: str = ""
    style: str = "INSTRUCTION"
    required_fields: Set[str] = field(default_factory=set)
    version: str = "1.0"

    def __post_init__(self):
        """Validate the template after initialization."""
        # Ensure all required fields are present in the template
        for field_name in self.required_fields:
            if f"{{{field_name}}}" not in self.template:
                raise ValueError(
                    f"Required field '{field_name}' not found in template '{self.name}'"
                )


class PromptStyle(str, Enum):
    """Supported prompt styles for different use cases."""

    INSTRUCTION = "instruction"
    CHAT = "chat"
    COMPLETION = "completion"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    SYSTEM = "system"


@dataclass
class KnowledgeItem:
    """A single piece of knowledge with metadata.

    Attributes:
        content: The main content/text of the knowledge
        source: Source identifier or description
        metadata: Additional metadata as key-value pairs
        score: Optional relevance score (0.0 to 1.0)
    """

    content: str
    source: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: Optional[float] = None


@dataclass
class SearchResult:
    """Result of a knowledge base search.

    Attributes:
        items: List of matching knowledge items
        total: Total number of matches found
        query: The original search query
        metadata: Additional search metadata
    """

    items: List[KnowledgeItem]
    total: int
    query: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EditSuggestion:
    """A suggested edit to a piece of content.

    Attributes:
        content: The suggested content
        confidence: Confidence score (0.0 to 1.0)
        reason: Explanation for the suggestion
        metadata: Additional metadata
    """

    content: str
    confidence: float
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingStats:
    """Statistics about a processing operation.

    Attributes:
        start_time: Timestamp when processing started
        end_time: Timestamp when processing ended
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        tokens_used: Number of tokens used
        metadata: Additional statistics
    """

    start_time: float
    end_time: float
    cache_hits: int = 0
    cache_misses: int = 0
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Get the duration of the operation in seconds."""
        return self.end_time - self.start_time

    @property
    def cache_hit_rate(self) -> float:
        """Get the cache hit rate (0.0 to 1.0)."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
