"""
Example of using SelfEditor with KnowledgeAwareStrategy.

This example demonstrates how to:
1. Create and populate a KnowledgeBase
2. Create a KnowledgeAwareStrategy with the knowledge base
3. Use it with the SelfEditor to analyze and improve code
4. Apply the suggested edits
"""

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the project root to the path so we can import evoseal
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase
from evoseal.integration.seal.self_editor.self_editor import (
    KnowledgeAwareStrategy,
    SelfEditor,
)
from evoseal.integration.seal.self_editor.models import (
    EditCriteria,
    EditOperation,
    EditSuggestion,
)


def setup_knowledge_base() -> KnowledgeBase:
    """Set up a knowledge base with example content for code improvement."""
    import tempfile

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


def print_suggestions(suggestions: List[EditSuggestion]) -> None:
    """Print the suggestions in a user-friendly format."""
    if not suggestions:
        print("\n✅ No suggestions available. The code looks good!")
        return

    print("\n🔍 Found", len(suggestions), "suggestions for improvement:")

    # Group suggestions by category
    by_category: Dict[str, List[EditSuggestion]] = {}
    for suggestion in suggestions:
        if not hasattr(suggestion, "criteria") or not suggestion.criteria:
            category = "Other"
        else:
            # Use the first criteria as the main category
            category = suggestion.criteria[0].value.replace("_", " ").title()

        if category not in by_category:
            by_category[category] = []
        by_category[category].append(suggestion)

    # Print suggestions by category
    for category, category_suggestions in by_category.items():
        print(f"\n📌 {category}:")
        for i, suggestion in enumerate(category_suggestions, 1):
            if not isinstance(suggestion, EditSuggestion):
                print(f"  {i}. [INVALID SUGGESTION] {suggestion}")
                continue

            # Print the main suggestion info
            print(
                f"  {i}. {suggestion.operation.value.upper()}: {suggestion.explanation}"
            )

            # Show criteria if available
            if hasattr(suggestion, "criteria") and suggestion.criteria:
                criteria = ", ".join(c.value for c in suggestion.criteria)
                print(f"     - Criteria: {criteria}")

            # Show confidence if available
            if hasattr(suggestion, "confidence"):
                print(f"     - Confidence: {suggestion.confidence:.1f}/1.0")

            # Show before/after for non-trivial changes
            if hasattr(suggestion, "original_text") and hasattr(
                suggestion, "suggested_text"
            ):
                if suggestion.original_text != suggestion.suggested_text:
                    print("     - Before:")
                    for line in str(suggestion.original_text).split("\n"):
                        if line.strip():
                            print(f"       | {line}")
                    print("     - After:")
                    for line in str(suggestion.suggested_text).split("\n"):
                        if line.strip():
                            print(f"       | {line}")
            print()  # Add spacing between suggestions


def apply_suggestions_interactive(
    editor: SelfEditor, content: str, suggestions: List[EditSuggestion]
) -> str:
    """Apply suggestions with user confirmation."""
    if not suggestions:
        return content

    print("\n" + "=" * 80)
    print("APPLYING SUGGESTIONS".center(80))
    print("=" * 80)

    # Create a content ID for tracking edits
    content_id = "interactive_edits"

    # Initialize the content in the editor
    editor.evaluate_content(content, content_id=content_id)
    edited_content = content

    for i, suggestion in enumerate(suggestions, 1):
        if not isinstance(suggestion, EditSuggestion):
            continue

        print(
            f"\nSuggestion {i}/{len(suggestions)}: {suggestion.operation.value.upper()}"
        )
        print(f"- {suggestion.explanation}")

        if hasattr(suggestion, "original_text") and hasattr(
            suggestion, "suggested_text"
        ):
            if suggestion.original_text != suggestion.suggested_text:
                print("\nBefore:")
                print(suggestion.original_text)
                print("\nAfter:")
                print(suggestion.suggested_text)

        apply = input("\nApply this change? [y/n] ").strip().lower()
        if apply == "y":
            # Apply the edit using the editor's apply_edit method
            edited_content = editor.apply_edit(
                content_id=content_id, suggestion=suggestion, apply=True
            )
            print("✅ Change applied")
        else:
            # Record that we're skipping this suggestion
            editor.apply_edit(content_id=content_id, suggestion=suggestion, apply=False)
            print("⏩ Skipped")

    # Get the final edited content
    edited_content = editor.get_current_content(content_id)
    return edited_content


def main():
    print("🔧 Setting up KnowledgeBase with example content...")
    kb = setup_knowledge_base()

    print("🚀 Creating KnowledgeAwareStrategy...")
    strategy = KnowledgeAwareStrategy(knowledge_base=kb)

    print("🛠️  Initializing SelfEditor...")
    editor = SelfEditor(strategy=strategy)

    # Get example content
    content = get_example_content()

    print("\n" + "=" * 80)
    print("ORIGINAL CONTENT".center(80))
    print("=" * 80)
    print(content)

    # Get edit suggestions
    print("\n🔍 Analyzing code and generating suggestions...")
    # Use evaluate_content with a content_id to track history
    content_id = "example_code"
    suggestions = editor.evaluate_content(content, content_id=content_id)

    # Print the suggestions
    print_suggestions(suggestions)

    # Apply suggestions interactively
    if suggestions and isinstance(suggestions[0], EditSuggestion):
        edited_content = apply_suggestions_interactive(editor, content, suggestions)

        print("\n" + "=" * 80)
        print("FINAL EDITED CONTENT".center(80))
        print("=" * 80)
        print(edited_content)

    # Show edit history
    print("\n" + "=" * 80)
    print("EDIT HISTORY".center(80))
    print("=" * 80)
    # Use the same content_id that was used for evaluation
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
