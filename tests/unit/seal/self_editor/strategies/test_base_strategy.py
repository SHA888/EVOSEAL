"""Regression tests for BaseEditStrategy.apply() empty original_text bug.

Bug: when original_text is "", `"" in content` is always True in Python, so
apply() hit `content.replace("", suggested_text)` which inserts suggested_text
at every character boundary, corrupting/bloating the content.

Fix: apply() now checks for empty original_text and prepends suggested_text
(matching SelfEditor.apply_edit ADD semantics) instead of calling replace.
"""

import pytest

from evoseal.integration.seal.self_editor.models import EditCriteria, EditOperation, EditSuggestion
from evoseal.integration.seal.self_editor.strategies.code_style_strategy import CodeStyleStrategy
from evoseal.integration.seal.self_editor.strategies.documentation_strategy import (
    DocumentationStrategy,
)


@pytest.fixture
def strategy():
    """Concrete strategy for testing apply() in isolation."""
    return CodeStyleStrategy()


class TestEmptyOriginalText:
    """apply() must not corrupt content when original_text is empty."""

    def test_empty_original_nonempty_suggested_prepends(self, strategy):
        """Empty original_text + non-empty suggested_text => prepend."""
        content = "hello world"
        suggestion = EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION],
            original_text="",
            suggested_text="prefix: ",
        )
        result = strategy.apply(content, suggestion)
        assert result == "prefix: hello world"

    def test_empty_original_empty_suggested_noop(self, strategy):
        """Empty original_text + empty suggested_text => no change."""
        content = "unchanged"
        suggestion = EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION],
            original_text="",
            suggested_text="",
        )
        result = strategy.apply(content, suggestion)
        assert result == "unchanged"

    def test_empty_original_does_not_bloat(self, strategy):
        """Must not call content.replace('', text) which would insert at every char boundary."""
        content = "abcd"
        suggestion = EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.DOCUMENTATION],
            original_text="",
            suggested_text="X",
        )
        result = strategy.apply(content, suggestion)
        # If the bug were present, result would be "XaXbXcXdX" (len 9).
        # Correct behavior: prepend => "Xabcd" (len 5).
        assert result == "Xabcd"
        assert len(result) == len(content) + len("X")


class TestDocumentationStrategyApplyIntegration:
    """Verify DocumentationStrategy-generated ADD suggestions work via apply()."""

    def test_missing_function_docstring_suggestion_via_apply(self):
        """A DocumentationStrategy ADD suggestion with empty original_text
        must produce a valid docstring insertion, not corrupted content."""
        strategy = DocumentationStrategy()
        content = "def foo():\n    pass\n"
        suggestions = strategy.evaluate(content)

        # Find the function docstring ADD suggestion
        add_suggestions = [
            s
            for s in suggestions
            if s.operation == EditOperation.ADD
            and "Missing docstring for function 'foo'" in s.explanation
        ]
        assert len(add_suggestions) >= 1, "Expected a missing-function-docstring suggestion"

        suggestion = add_suggestions[0]
        assert suggestion.original_text == ""

        result = strategy.apply(content, suggestion)

        # The docstring text should appear in the result exactly once,
        # prepended — not inserted before every character.
        assert suggestion.suggested_text in result
        assert result.count(suggestion.suggested_text) == 1
        # Content should be longer than original by roughly the docstring size,
        # not massively bloated.
        assert len(result) < len(content) + len(suggestion.suggested_text) + 5

    def test_missing_class_docstring_suggestion_via_apply(self):
        """Same as above but for a class docstring ADD suggestion."""
        strategy = DocumentationStrategy()
        content = "class Bar:\n    pass\n"
        suggestions = strategy.evaluate(content)

        add_suggestions = [
            s
            for s in suggestions
            if s.operation == EditOperation.ADD
            and "Missing docstring for class 'Bar'" in s.explanation
        ]
        assert len(add_suggestions) >= 1

        suggestion = add_suggestions[0]
        assert suggestion.original_text == ""

        result = strategy.apply(content, suggestion)
        assert suggestion.suggested_text in result
        assert result.count(suggestion.suggested_text) == 1
