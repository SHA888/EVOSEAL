"""Example of using SelfEditor with KnowledgeAwareStrategy.

This example demonstrates how to:
1. Create and populate a KnowledgeBase
2. Create a KnowledgeAwareStrategy with the knowledge base
3. Use it with the SelfEditor to analyze and improve code
4. Apply the suggested edits
"""

from __future__ import annotations

# Standard library imports
import os
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, List, Optional, Union, cast

# Add the project root to the path so we can import evoseal
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Third-party imports
# Local application imports
from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase
from evoseal.integration.seal.self_editor.models import EditCriteria, EditOperation
from evoseal.integration.seal.self_editor.models import (
    EditSuggestion as ModelsEditSuggestion,
)
from evoseal.integration.seal.self_editor.self_editor import (
    EditSuggestion as EditorEditSuggestion,
)
from evoseal.integration.seal.self_editor.self_editor import SelfEditor
from evoseal.integration.seal.self_editor.strategies.knowledge_aware_strategy import (
    KnowledgeAwareStrategy,
)
from evoseal.integration.seal.self_editor.utils.code_utils import (
    apply_edit,
    apply_edits,
    get_line_range,
    get_line_ranges,
)

# Type alias for either type of EditSuggestion
AnyEditSuggestion = Union[ModelsEditSuggestion, EditorEditSuggestion, dict[str, Any]]
AnyEditSuggestionList = List[AnyEditSuggestion]


def setup_knowledge_base() -> KnowledgeBase:
    """Sets up a knowledge base with example content for code improvement.

    Returns:
        KnowledgeBase: A knowledge base with example content.
    """
    # Create a temporary directory for the knowledge base
    temp_dir = tempfile.mkdtemp(prefix="evoseal_kb_")
    kb_path = os.path.join(temp_dir, "knowledge_base.db")

    # Initialize the KnowledgeBase with the temporary path
    kb = KnowledgeBase(storage_path=kb_path)

    # Add knowledge entries
    kb.add_entry(
        "Python Function Best Practices: Use descriptive function names with lowercase and underscores, "
        "include type hints, add docstrings, keep functions small and focused, use meaningful variable names, "
        "handle exceptions, and follow PEP 8 style guide.",
        tags=["python", "best-practices", "functions"],
    )

    kb.add_entry(
        "Security Best Practices: Avoid using eval() and exec() with untrusted input, use parameterized queries, "
        "validate and sanitize inputs, use environment variables for sensitive data, keep dependencies updated, "
        "and implement proper authentication and authorization.",
        tags=["security", "best-practices"],
    )

    kb.add_entry(
        "Error Handling in Python: Use specific exceptions, create custom exception classes, include context in "
        "error messages, use try/except blocks appropriately, log exceptions with stack traces, and clean up "
        "resources using context managers or finally blocks.",
        tags=["python", "error-handling", "best-practices"],
    )

    kb.add_entry(
        "Python Type Hints: Use type hints for function parameters and return values, leverage typing module, "
        "use TypeVar for generic functions, consider Protocol for structural subtyping, use @overload for "
        "multiple signatures, and add type hints to class attributes.",
        tags=["python", "type-hints", "best-practices"],
    )

    kb.add_entry(
        "Python Performance Tips: Use list comprehensions, leverage built-in functions, use generators for large "
        "datasets, prefer local variables, use sets/dictionaries for O(1) lookups, and consider lru_cache.",
        tags=["python", "performance", "optimization"],
    )

    kb.add_entry(
        "Keep functions small and focused on doing one thing well (Single Responsibility Principle).",
        tags=["functions", "best-practices", "clean-code"],
    )

    return kb


def get_example_content() -> str:
    """Return example Python code with various issues for demonstration."""
    return """
# Example module with some Python code that could use improvement

import os
from typing import *

def add_numbers(a, b):
    # This function adds two numbers
    return a + b

class DataProcessor:
    def process(self, data):
        # TODO: Implement data validation
        # FIXME: Handle empty input case
        return [x * 2 for x in data if x % 2 == 0]

    def calculate_statistics(self, numbers):
        # Calculate basic statistics
        total = sum(numbers)
        count = len(numbers)
        avg = total / count if count > 0 else 0
        return {"total": total, "count": count, "average": avg}

def process_data(data, threshold=0.5):
    # Process data with threshold
    if not data:
        return []
    return [d for d in data if d > threshold]

def get_user_input():
    # Potentially unsafe input handling
    user_input = input("Enter some Python code: ")
    result = eval(user_input)  # Security risk!
    print(f"Result: {result}")
    return result

# Example of a function that could use type hints
def process_items(items):
    return [item.upper() for item in items if isinstance(item, str)]
"""


def print_suggestions(suggestions: list[AnyEditSuggestion]) -> None:
    """Print the suggestions in a user-friendly format.

    Args:
        suggestions: A list of EditSuggestion objects or compatible dicts
    """
    if not suggestions:
        print("No suggestions to display.")
        return

    # Group suggestions by category
    by_category: dict[str, list[AnyEditSuggestion]] = {}
    for suggestion in suggestions:
        if isinstance(suggestion, dict):
            category = str(suggestion.get("criteria", "Other"))
        elif hasattr(suggestion, "criteria") and suggestion.criteria:
            category = str(suggestion.criteria)
        else:
            category = "Other"
        by_category.setdefault(category, []).append(suggestion)

    # Print suggestions by category
    for category, category_suggestions in by_category.items():
        print(f"\n{category}:")
        print("-" * len(category))
        for i, suggestion in enumerate(category_suggestions, 1):
            if isinstance(suggestion, dict):
                desc = suggestion.get("description", "No description")
                print(f"\n{i}. {desc}")
                if (
                    "line_number" in suggestion
                    and suggestion["line_number"] is not None
                ):
                    print(f"   Line: {suggestion['line_number']}")
                if "original" in suggestion and "suggested" in suggestion:
                    print("   Original:")
                    print(f"     {suggestion['original']}")
                    print("   Suggested:")
                    print(f"     {suggestion['suggested']}")
                if "explanation" in suggestion:
                    print(f"   Explanation: {suggestion['explanation']}")
                if "severity" in suggestion:
                    print(f"   Severity: {suggestion['severity']}")
            else:
                # Handle both ModelsEditSuggestion and EditorEditSuggestion
                desc = getattr(suggestion, "description", "No description")
                print(f"\n{i}. {desc}")

                line_number = getattr(suggestion, "line_number", None)
                if line_number is not None:
                    print(f"   Line: {line_number}")

                if hasattr(suggestion, "original") and hasattr(suggestion, "suggested"):
                    print("   Original:")
                    print(f"     {suggestion.original}")
                    print("   Suggested:")
                    print(f"     {suggestion.suggested}")
                elif hasattr(suggestion, "code_snippet"):
                    print("   Code:")
                    print(f"     {suggestion.code_snippet}")

                explanation = getattr(suggestion, "explanation", None)
                if explanation:
                    print(f"   Explanation: {explanation}")

                severity = getattr(suggestion, "severity", None)
                if severity:
                    print(f"   Severity: {severity}")


def apply_suggestions_interactive(
    editor: SelfEditor, content: str, suggestions: list[AnyEditSuggestion]
) -> str:
    """Apply suggestions with user confirmation.

    Args:
        editor: The SelfEditor instance
        content: The original content
        suggestions: List of suggestions to apply (EditSuggestion objects or dicts)

    Returns:
        The modified content after applying selected suggestions
    """
    if not suggestions:
        print("No suggestions to apply.")
        return content

    print(f"\nFound {len(suggestions)} suggestions:")
    for i, suggestion in enumerate(suggestions, 1):
        print(f"\nSuggestion {i}:")
        if isinstance(suggestion, dict):
            print(f"- Type: {suggestion.get('type', 'N/A')}")
            print(f"- Description: {suggestion.get('description', 'No description')}")
            print(f"- Location: {suggestion.get('line_number', 'N/A')}")
            print(f"- Original: {suggestion.get('original', 'N/A')}")
            print(f"- Suggested: {suggestion.get('suggested', 'N/A')}")
        else:
            print(f"- Type: {getattr(suggestion, 'type', 'N/A')}")
            print(
                f"- Description: {getattr(suggestion, 'description', 'No description')}"
            )
            print(f"- Location: {getattr(suggestion, 'line_number', 'N/A')}")
            if hasattr(suggestion, "original") and hasattr(suggestion, "suggested"):
                print(f"- Original: {suggestion.original}")
                print(f"- Suggested: {suggestion.suggested}")

    while True:
        try:
            choice = input(
                "\nEnter the number of the suggestion to apply, 'a' for all, or 'q' to quit: "
            ).lower()

            if choice == "q":
                return content

            if choice == "a":
                return _apply_all_suggestions(editor, content, suggestions)

            idx = int(choice) - 1
            if 0 <= idx < len(suggestions):
                return _apply_single_suggestion(editor, content, suggestions[idx])

            print(f"Invalid choice: {choice}. Please try again.")
        except ValueError:
            print("Please enter a valid number, 'a' for all, or 'q' to quit.")


def _apply_all_suggestions(
    editor: SelfEditor, content: str, suggestions: list[AnyEditSuggestion]
) -> str:
    """Apply all suggestions to the content."""
    edited_content = content
    for i, suggestion in enumerate(suggestions, 1):
        print(f"\nApplying suggestion {i}/{len(suggestions)}...")
        if isinstance(suggestion, dict):
            edited_content = apply_edit(
                edited_content,
                EditOperation.REPLACE,
                suggestion["line_number"],
                suggestion["original"],
                suggestion["suggested"],
            )
        else:
            result = editor.apply_edit(
                content_id="interactive_edits", suggestion=suggestion, apply=True
            )
            if result is not None:
                edited_content = result
    return edited_content


def _apply_single_suggestion(
    editor: SelfEditor, content: str, suggestion: AnyEditSuggestion
) -> str:
    """Apply a single suggestion to the content."""
    if isinstance(suggestion, dict):
        return apply_edit(
            content,
            EditOperation.REPLACE,
            suggestion["line_number"],
            suggestion["original"],
            suggestion["suggested"],
        )

    # Convert ModelsEditSuggestion to EditorEditSuggestion if needed
    if isinstance(suggestion, ModelsEditSuggestion):
        suggestion_dict = asdict(suggestion)
        suggestion = EditorEditSuggestion(
            operation=EditOperation(suggestion_dict["operation"]),
            original_text=suggestion_dict["original_text"],
            suggested_text=suggestion_dict["suggested_text"],
            line_number=suggestion_dict["line_number"],
            explanation=suggestion_dict.get("explanation", ""),
        )

    result = editor.apply_edit(
        content_id="interactive_edit",
        suggestion=cast(EditorEditSuggestion, suggestion),
        apply=True,
    )
    return result if result is not None else content


def main() -> None:
    print("🔧 Setting up KnowledgeBase with example content...")
    knowledge_base = setup_knowledge_base()

    # Create a KnowledgeAwareStrategy with the knowledge base
    strategy = KnowledgeAwareStrategy(knowledge_base=knowledge_base)

    # Create a SelfEditor with the strategy
    editor = SelfEditor(strategy=strategy)

    # Example code to analyze and improve
    content = """
def calculate_sum(a, b):
    # Add two numbers
    return a + b

print(calculate_sum(5, 10))  # This should print 15
"""

    # Get edit suggestions
    print("\n🔍 Analyzing code and generating suggestions...")

    # Use evaluate_content with a content_id to track history
    content_id = "example_code"
    print("\nAnalyzing code...")
    suggestions = editor.evaluate_content(content, content_id=content_id)

    # Print suggestions
    suggestions_list = (
        list(suggestions) if not isinstance(suggestions, list) else suggestions
    )
    print_suggestions(suggestions_list)

    # Interactive application of suggestions
    if suggestions_list:
        # Apply suggestions interactively
        edited_content = apply_suggestions_interactive(
            editor, content, suggestions_list
        )
        print("\n" + "=" * 80)
        print("FINAL EDITED CONTENT".center(80))
        print("=" * 80)
        print(edited_content)
    history = editor.get_edit_history(content_id=content_id)
    if history:
        for i, entry in enumerate(history, 1):
            # Handle both tuple and object-style entries for backward compatibility
            if isinstance(entry, tuple) and len(entry) >= 2:
                operation, description = entry[0], entry[1]
                operation_str = (
                    str(operation.value)
                    if hasattr(operation, "value")
                    else str(operation)
                )
                print(f"{i}. {operation_str}: {description}")
            elif hasattr(entry, "operation") and hasattr(entry, "description"):
                operation_str = (
                    str(entry.operation.value)
                    if hasattr(entry.operation, "value")
                    else str(entry.operation)
                )
                print(f"{i}. {operation_str}: {entry.description}")
            else:
                print(f"{i}. {str(entry)}")
    else:
        print("No edit history available.")

    print("\n✨ Analysis complete!")


if __name__ == "__main__":
    main()
