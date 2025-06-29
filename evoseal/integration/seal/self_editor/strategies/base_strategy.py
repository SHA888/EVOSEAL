"""Base strategy class for all editing strategies."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from ..models import EditCriteria, EditOperation, EditSuggestion


class BaseEditStrategy(ABC):
    """Abstract base class for all editing strategies.

    Subclasses should implement the evaluate method to provide specific
    editing functionality.
    """

    def __init__(self, priority: int = 0, enabled: bool = True):
        """Initialize the strategy with priority and enabled state.

        Args:
            priority: Priority of the strategy (higher means it runs first)
            enabled: Whether the strategy is enabled
        """
        self.priority = priority
        self.enabled = enabled

    @abstractmethod
    def evaluate(self, content: str, **kwargs: Any) -> list[EditSuggestion]:
        """Evaluate content and return edit suggestions.

        Args:
            content: The content to evaluate
            **kwargs: Additional context or parameters

        Returns:
            List of EditSuggestion objects
        """
        pass

    def apply(self, content: str, suggestion: EditSuggestion) -> str:
        """Apply a single suggestion to content.

        Args:
            content: The content to modify
            suggestion: The suggestion to apply

        Returns:
            Modified content with the suggestion applied
        """
        if not suggestion or not self.enabled:
            return content

        if hasattr(suggestion, "original_text") and hasattr(suggestion, "suggested_text"):
            if suggestion.original_text in content:
                return content.replace(suggestion.original_text, suggestion.suggested_text)
        return content

    def get_config(self) -> dict[str, Any]:
        """Get the current configuration of the strategy.

        Returns:
            Dictionary containing strategy configuration
        """
        return {
            "strategy_name": self.__class__.__name__,
            "priority": self.priority,
            "enabled": self.enabled,
        }

    def update_config(self, **kwargs: Any) -> None:
        """Update strategy configuration.

        Args:
            **kwargs: Configuration options to update
        """
        if "priority" in kwargs:
            self.priority = kwargs["priority"]
        if "enabled" in kwargs:
            self.enabled = kwargs["enabled"]

    def __lt__(self, other: object) -> bool:
        """Compare strategies by priority for sorting.

        Args:
            other: The other strategy to compare with

        Returns:
            bool: True if this strategy has higher priority than the other

        Raises:
            TypeError: If other is not a BaseEditStrategy
        """
        if not isinstance(other, BaseEditStrategy):
            return NotImplemented
        return self.priority > other.priority
