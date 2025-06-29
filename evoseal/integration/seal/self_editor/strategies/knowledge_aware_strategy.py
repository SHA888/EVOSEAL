"""
Knowledge-Aware Edit Strategy for SelfEditor.

This module provides a strategy that uses the KnowledgeBase to provide
context-aware editing suggestions.
"""

from __future__ import annotations

from typing import Any, Optional

from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase
from evoseal.integration.seal.self_editor.self_editor import (
    DefaultEditStrategy,
    EditCriteria,
    EditOperation,
    EditStrategy,
    EditSuggestion,
)


class KnowledgeAwareStrategy(EditStrategy):
    """
    An editing strategy that uses KnowledgeBase for context-aware suggestions.

    This strategy enhances the default strategy by querying the KnowledgeBase
    for relevant context before making editing suggestions.
    """

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        min_similarity: float = 0.3,
        max_context_entries: int = 3,
        default_strategy: DefaultEditStrategy | None = None,
        **kwargs: Any,
    ):
        """Initialize the KnowledgeAwareStrategy.

        Args:
            knowledge_base: The KnowledgeBase instance to use for context.
            min_similarity: Minimum similarity score (0.0 to 1.0) for context to be considered relevant.
            max_context_entries: Maximum number of context entries to consider.
            default_strategy: Optional DefaultEditStrategy instance to use. If not provided,
                           a new instance will be created.
            **kwargs: Additional arguments passed to the parent class.

        Raises:
            ValueError: If min_similarity is not between 0.0 and 1.0.
        """
        if not 0.0 <= min_similarity <= 1.0:
            raise ValueError("min_similarity must be between 0.0 and 1.0")

        super().__init__(**kwargs)
        self.knowledge_base = knowledge_base
        self.min_similarity = min_similarity
        self.max_context_entries = max_context_entries
        self._default_strategy = default_strategy or DefaultEditStrategy()

    def get_relevant_context(self, content: str) -> list[dict[str, Any]]:
        """Retrieve relevant context from the KnowledgeBase.

        Args:
            content: The content to find context for.

        Returns:
            List of relevant context entries from the KnowledgeBase as dictionaries.
        """
        # Simple implementation - can be enhanced with more sophisticated search
        entries = self.knowledge_base.search_entries(query=content, limit=self.max_context_entries)
        # Convert KnowledgeEntry objects to dictionaries
        return [entry.to_dict() if hasattr(entry, "to_dict") else entry for entry in entries]

    def _analyze_content_with_context(
        self, content: str, context_entries: list[dict[str, Any]]
    ) -> list[EditSuggestion]:
        """Analyze content using context from the knowledge base.

        Args:
            content: The content to analyze.
            context_entries: List of relevant context entries from the knowledge base.

        Returns:
            List of suggested edits based on the analysis.
        """
        suggestions: list[EditSuggestion] = []
        lines = content.split("\n")
        current_function: str | None = None

        # First, analyze the entire content for high-level patterns
        self._analyze_imports(content, suggestions)

        # Then analyze each line
        for i, line in enumerate(lines):
            line = line.rstrip()
            if not line.strip():
                continue

            # Track current function for context
            if line.strip().startswith("def "):
                current_function = line.strip().split("(")[0].split()[-1]

            # Analyze the line for potential improvements
            self._analyze_line(i, line, lines, current_function, suggestions)

        # After analyzing all lines, do cross-line analysis
        self._analyze_functions(content, lines, suggestions)

        # Add suggestions based on knowledge base context
        if context_entries:
            self._add_context_based_suggestions(content, context_entries, suggestions)

        return suggestions

    def _analyze_line(
        self,
        line_num: int,
        line: str,
        lines: list[str],
        current_function: str | None,
        suggestions: list[EditSuggestion],
    ) -> None:
        """Analyze a single line for potential improvements."""
        # Check for function definitions
        if line.strip().startswith("def "):
            self._analyze_function_definition(line_num, line, lines, suggestions)

        # Check for TODO/FIXME comments
        elif any(marker in line for marker in ["TODO", "FIXME", "XXX"]):
            suggestions.append(
                EditSuggestion(
                    operation=EditOperation.CLARIFY,
                    criteria=[EditCriteria.COMPLETENESS, EditCriteria.ACCURACY],
                    original_text=line,
                    suggested_text=line,
                    confidence=0.8,
                    explanation=f"Address comment: {line.strip()}",
                )
            )

        # Check for potential security issues
        elif any(
            unsafe in line
            for unsafe in [
                "eval(",
                "exec(",
                "pickle.loads(",
                "subprocess.call(",
                "os.system(",
            ]
        ):
            suggestions.append(
                EditSuggestion(
                    operation=EditOperation.REWRITE,
                    criteria=[EditCriteria.SECURITY, EditCriteria.BEST_PRACTICE],
                    original_text=line,
                    suggested_text=f"# SECURITY: {line}",
                    confidence=0.95,
                    explanation="Potentially unsafe code detected. Consider using safer alternatives.",
                )
            )

        # Check for print statements (suggest using logging instead)
        elif line.strip().startswith("print(") and not any(
            skip in line for skip in ["# noqa", "# no-print"]
        ):
            suggestions.append(
                EditSuggestion(
                    operation=EditOperation.REWRITE,
                    criteria=[EditCriteria.BEST_PRACTICE, EditCriteria.PERFORMANCE],
                    original_text=line,
                    suggested_text=f"# TODO: Replace print with proper logging\n# {line}",
                    confidence=0.8,
                    explanation="Consider using the logging module instead of print statements for production code",
                )
            )

    def _analyze_function_definition(
        self,
        line_num: int,
        line: str,
        lines: list[str],
        suggestions: list[EditSuggestion],
    ) -> None:
        """Analyze a function definition for potential improvements."""
        func_def = line.strip()
        func_name = func_def.split("(")[0].split()[-1]

        # Check for missing return type hints
        if "->" not in func_def and "):" in func_def:
            return_type = self._infer_return_type(func_name)
            new_line = func_def.replace("):", f") -> {return_type}:")

            # Find the original indentation
            indent = len(line) - len(line.lstrip())
            new_line = " " * indent + new_line

            suggestions.append(
                EditSuggestion(
                    operation=EditOperation.REWRITE,
                    criteria=[EditCriteria.CLARITY, EditCriteria.STYLE],
                    original_text=line,
                    suggested_text=new_line,
                    confidence=0.85,
                    explanation=f"Add return type hint to function '{func_name}'",
                )
            )

        # Check for missing docstrings
        if line_num + 1 < len(lines) and not lines[line_num + 1].strip().startswith('"""'):
            self._add_docstring_suggestion(line, func_def, func_name, suggestions)

    def _infer_return_type(self, func_name: str) -> str:
        """Infer the return type based on function name patterns."""
        if func_name.startswith(("is_", "has_", "can_", "should_")):
            return "bool"
        elif func_name.startswith(("get_", "find_", "load_", "fetch_")):
            return "Any | None"
        elif func_name.startswith(("process_", "handle_", "save_", "update_", "delete_")):
            return "None"
        elif func_name.startswith(("create_", "make_", "build_", "generate_")):
            return "Any"
        return "Any"

    def _add_docstring_suggestion(
        self,
        line: str,
        func_def: str,
        func_name: str,
        suggestions: list[EditSuggestion],
    ) -> None:
        """Add a suggestion for a missing docstring."""
        indent = len(line) - len(line.lstrip())
        indent_str = " " * indent

        # Create a basic docstring
        docstring = f'{indent_str}"""{func_name}.'

        # Add parameter info if available
        if "(" in func_def and ")" in func_def:
            params = func_def.split("(")[1].split(")")[0]
            if params and params != "self":
                docstring += "\n\n    Args:"
                for param in params.split(","):
                    param = param.strip()
                    if param == "self":
                        continue
                    param_name = param.split(":")[0].strip()  # Handle type hints
                    docstring += f"\n        {param_name}: Description of {param_name}."

        # Add return section if there's a return type hint
        if "->" in func_def and "-> None" not in func_def:
            docstring += "\n\n    Returns:"
            docstring += "\n        Description of the return value."

        docstring += f'\n{indent_str}"""'

        suggestions.append(
            EditSuggestion(
                operation=EditOperation.ADD,
                criteria=[EditCriteria.DOCUMENTATION, EditCriteria.CLARITY],
                original_text=line,
                suggested_text=f"{line}\n{docstring}",
                confidence=0.9,
                explanation=f"Add docstring to function '{func_name}'",
            )
        )

    def _analyze_imports(self, content: str, suggestions: list[EditSuggestion]) -> None:
        """Analyze imports for potential improvements."""
        if "import *" in content and "# noqa" not in content:
            suggestions.append(
                EditSuggestion(
                    operation=EditOperation.REWRITE,
                    criteria=[EditCriteria.BEST_PRACTICE, EditCriteria.CLARITY],
                    original_text=content,
                    suggested_text=content.replace("import *", "import *  # noqa: F403, F401"),
                    confidence=0.9,
                    explanation="Avoid wildcard imports as they can lead to namespace pollution",
                )
            )

    def _analyze_functions(
        self, content: str, lines: list[str], suggestions: list[EditSuggestion]
    ) -> None:
        """Analyze functions for potential improvements."""
        # Check for missing error handling in functions
        if "def " in content and "try:" not in content and "except " not in content:
            functions = [line for line in lines if line.strip().startswith("def ")]
            for func_def in functions:
                func_name = func_def.split("(")[0].split()[-1]
                if func_name not in [
                    "__init__",
                    "main",
                    "test_",
                ]:  # Skip common functions that might not need try/except
                    suggestions.append(
                        EditSuggestion(
                            operation=EditOperation.ADD,
                            criteria=[
                                EditCriteria.ROBUSTNESS,
                                EditCriteria.ERROR_HANDLING,
                            ],
                            original_text=content,
                            suggested_text=content,
                            confidence=0.7,
                            explanation=f"Consider adding error handling in function '{func_name}'",
                        )
                    )

    def _add_context_based_suggestions(
        self,
        content: str,
        context_entries: list[dict[str, Any]],
        suggestions: list[EditSuggestion],
    ) -> None:
        """Add suggestions based on knowledge base context."""
        # Check for security-related context
        security_context = [
            e
            for e in context_entries
            if any(tag in e.get("tags", []) for tag in ["security", "best-practices"])
        ]

        if security_context and any(unsafe in content for unsafe in ["input(", "eval(", "exec("]):
            suggestions.append(
                EditSuggestion(
                    operation=EditOperation.CLARIFY,
                    criteria=[EditCriteria.SECURITY],
                    original_text=content,
                    suggested_text=f"# SECURITY: {content}",
                    confidence=0.9,
                    explanation="Potential security issue detected based on knowledge base context",
                )
            )

    def evaluate(self, content: str, **kwargs: Any) -> list[EditSuggestion]:
        """Evaluate content and return suggested edits with KnowledgeBase context.

        Args:
            content: The content to evaluate.
            **kwargs: Additional arguments for evaluation.

        Returns:
            List of suggested edits.
        """
        # Get relevant context from KnowledgeBase
        context_entries = self.get_relevant_context(content)

        # Get suggestions from the knowledge-aware analysis
        knowledge_suggestions = self._analyze_content_with_context(content, context_entries)

        # Get suggestions from the default strategy
        default_suggestions = self._default_strategy.evaluate(content, **kwargs)

        # Combine and deduplicate suggestions
        all_suggestions = {}

        # Add knowledge-based suggestions first
        for suggestion in knowledge_suggestions:
            key = (
                suggestion.operation,
                suggestion.original_text,
                suggestion.suggested_text,
            )
            all_suggestions[key] = suggestion

        # Add default suggestions, keeping higher confidence scores for duplicates
        for suggestion in default_suggestions:
            key = (
                suggestion.operation,
                suggestion.original_text,
                suggestion.suggested_text,
            )
            if (
                key not in all_suggestions
                or suggestion.confidence > all_suggestions[key].confidence
            ):
                all_suggestions[key] = suggestion

        # Sort suggestions by confidence (highest first)
        return sorted(all_suggestions.values(), key=lambda x: x.confidence, reverse=True)

    def apply_edit(self, content: str, suggestion: EditSuggestion) -> str:
        """Apply a suggested edit to the content.

        Args:
            content: The content to edit.
            suggestion: The suggested edit to apply.

        Returns:
            The edited content.
        """
        return self._default_strategy.apply_edit(content, suggestion)
