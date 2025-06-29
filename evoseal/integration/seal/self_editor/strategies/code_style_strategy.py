"""Strategy for enforcing code style rules."""

import re
from typing import Any, Optional

from ..models import EditCriteria, EditOperation, EditSuggestion
from .base_strategy import BaseEditStrategy


class CodeStyleStrategy(BaseEditStrategy):
    """Strategy for enforcing consistent code style rules.

    This strategy checks for and enforces various code style rules such as:
    - Consistent indentation
    - Line length limits
    - Trailing whitespace
    - Consistent quote usage
    - And other PEP 8 style guidelines
    """

    def __init__(
        self,
        max_line_length: int = 88,
        indent_size: int = 4,
        use_spaces: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize the code style strategy.

        Args:
            max_line_length: Maximum allowed line length
            indent_size: Number of spaces per indentation level
            use_spaces: Whether to use spaces (True) or tabs (False)
            **kwargs: Additional arguments for BaseEditStrategy
        """
        super().__init__(**kwargs)
        self.max_line_length = max_line_length
        self.indent_size = indent_size
        self.use_spaces = use_spaces
        self.indent_char = " " * indent_size if use_spaces else "\t"

    def evaluate(self, content: str, **kwargs: Any) -> list[EditSuggestion]:
        """Evaluate content for code style violations.

        Args:
            content: The content to evaluate
            **kwargs: Additional context (e.g., file extension, language)

        Returns:
            List of EditSuggestion objects for style improvements
        """
        if not content or not self.enabled:
            return []

        suggestions = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1

            # Check line length
            if len(line) > self.max_line_length:
                suggestions.append(self._create_line_length_suggestion(line, line_num, len(line)))

            # Check for trailing whitespace
            if line.rstrip() != line:
                suggestions.append(self._create_trailing_whitespace_suggestion(line, line_num))

            # Check for mixed indentation
            if self._has_mixed_indentation(line):
                suggestions.append(self._create_mixed_indentation_suggestion(line, line_num))

        # Check for consistent quote usage
        if "'" in content and '"' in content:
            suggestions.extend(self._check_quote_consistency(content))

        return suggestions

    def _create_line_length_suggestion(
        self, line: str, line_num: int, length: int
    ) -> EditSuggestion:
        """Create suggestion for line length violation."""
        return EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.STYLE, EditCriteria.READABILITY],
            original_text=line,
            suggested_text=line[: self.max_line_length].rstrip() + "  # noqa: E501",
            explanation=f"Line {line_num} is too long ({length} > {self.max_line_length} characters)",
            confidence=0.9,
            line_number=line_num,
        )

    def _create_trailing_whitespace_suggestion(self, line: str, line_num: int) -> EditSuggestion:
        """Create suggestion for trailing whitespace."""
        return EditSuggestion(
            operation=EditOperation.REMOVE,
            criteria=[EditCriteria.STYLE],
            original_text=line,
            suggested_text=line.rstrip(),
            explanation=f"Line {line_num} has trailing whitespace",
            confidence=1.0,
            line_number=line_num,
        )

    def _has_mixed_indentation(self, line: str) -> bool:
        """Check if line has mixed tabs and spaces for indentation."""
        if not line or line[0] not in " \t":
            return False

        # Check for mixed tabs and spaces
        has_tabs = "\t" in line
        has_spaces = " " in line

        if has_tabs and has_spaces:
            # Check if spaces are only for alignment after tabs
            tab_pos = line.find("\t")
            space_pos = line.find(" ")
            return space_pos < tab_pos

        return False

    def _create_mixed_indentation_suggestion(self, line: str, line_num: int) -> EditSuggestion:
        """Create suggestion for mixed indentation."""
        # Replace tabs with spaces or vice versa based on configuration
        if self.use_spaces:
            new_line = line.replace("\t", " " * self.indent_size)
        else:
            # Convert spaces to tabs (group of 4 spaces to 1 tab)
            new_line = re.sub(r" " * self.indent_size, "\t", line)

        return EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.STYLE, EditCriteria.CONSISTENCY],
            original_text=line,
            suggested_text=new_line,
            explanation=f"Line {line_num} uses mixed indentation",
            confidence=1.0,
            line_number=line_num,
        )

    def _check_quote_consistency(self, content: str) -> list[EditSuggestion]:
        """Check for consistent quote usage."""
        # This is a simplified example - a real implementation would be more sophisticated
        suggestions = []

        # Look for patterns that might indicate inconsistent quotes
        # This is a basic check - a real implementation would use a proper parser
        single_quotes = content.count("'") - content.count("\\'")
        double_quotes = content.count('"') - content.count('\\"')

        if single_quotes > 0 and double_quotes > 0:
            suggestions.append(
                EditSuggestion(
                    operation=EditOperation.NOTE,
                    criteria=[EditCriteria.STYLE, EditCriteria.CONSISTENCY],
                    explanation="Mixed single and double quotes detected. Consider standardizing on one style.",
                    confidence=0.7,
                )
            )

        return suggestions

    def get_config(self) -> dict[str, Any]:
        """Get the current configuration of the strategy."""
        config = super().get_config()
        config.update(
            {
                "max_line_length": self.max_line_length,
                "indent_size": self.indent_size,
                "use_spaces": self.use_spaces,
            }
        )
        return config
