"""Tests for the SelfEditor component."""

from datetime import datetime

import pytest

from evoseal.integration.seal.self_editor import (
    DefaultEditStrategy,
    EditCriteria,
    EditHistoryEntry,
    EditOperation,
    EditSuggestion,
    SelfEditor,
)
from evoseal.integration.seal.self_editor.models import ContentState


class TestEditSuggestion:
    """Tests for the EditSuggestion class."""

    def test_edit_suggestion_creation(self):
        """Test creating an EditSuggestion instance."""
        suggestion = EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.ACCURACY, EditCriteria.CLARITY],
            original_text="is design to",
            suggested_text="is designed to",
            confidence=0.9,
            explanation="Correct verb form",
        )

        assert suggestion.operation == EditOperation.REWRITE
        assert EditCriteria.ACCURACY in suggestion.criteria
        assert EditCriteria.CLARITY in suggestion.criteria
        assert suggestion.original_text == "is design to"
        assert suggestion.suggested_text == "is designed to"
        assert suggestion.confidence == 0.9
        assert suggestion.explanation == "Correct verb form"

    def test_to_dict(self):
        """Test converting EditSuggestion to dictionary."""
        suggestion = EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.ACCURACY],
            original_text="is design to",
            suggested_text="is designed to",
            confidence=0.9,
        )

        data = suggestion.to_dict()
        assert data["operation"] == "rewrite"
        assert data["criteria"] == ["accuracy"]
        assert data["original_text"] == "is design to"
        assert data["suggested_text"] == "is designed to"
        assert data["confidence"] == 0.9

    def test_from_dict(self):
        """Test creating EditSuggestion from dictionary."""
        data = {
            "operation": "rewrite",
            "criteria": ["accuracy"],
            "original_text": "is design to",
            "suggested_text": "is designed to",
            "confidence": 0.9,
            "explanation": "Test",
        }

        suggestion = EditSuggestion.from_dict(data)
        assert suggestion.operation == EditOperation.REWRITE
        assert EditCriteria.ACCURACY in suggestion.criteria
        assert suggestion.original_text == "is design to"
        assert suggestion.suggested_text == "is designed to"
        assert suggestion.confidence == 0.9
        assert suggestion.explanation == "Test"


class TestContentState:
    """Tests for the ContentState class."""

    def test_add_edit(self):
        """Test adding an edit to the history."""
        content_state = ContentState(
            content_id="test_1",
            original_content="Original content",
            current_content="Current content",
        )

        suggestion = EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.ACCURACY],
            original_text="Original",
            suggested_text="Updated",
            confidence=0.9,
        )

        entry = EditHistoryEntry(
            timestamp=datetime.utcnow(),
            operation=suggestion.operation,
            content_id=content_state.content_id,
            suggestion=suggestion,
            applied=True,
        )

        content_state.add_history_entry(entry)
        content_state.current_content = "Updated"

        assert len(content_state.history) == 1
        assert content_state.current_content == "Updated"
        assert content_state.updated_at > content_state.created_at

    def test_add_edit_not_applied(self):
        """Test adding an edit that is not applied."""
        content_state = ContentState(
            content_id="test_1",
            original_content="Original content",
            current_content="Current content",
        )

        suggestion = EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.ACCURACY],
            original_text="Original",
            suggested_text="Updated",
            confidence=0.9,
        )

        entry = EditHistoryEntry(
            timestamp=datetime.utcnow(),
            operation=suggestion.operation,
            content_id=content_state.content_id,
            suggestion=suggestion,
            applied=False,
        )

        content_state.add_history_entry(entry)

        assert len(content_state.history) == 1
        assert content_state.current_content == "Current content"  # Should not change


class TestDefaultEditStrategy:
    """Tests for the DefaultEditStrategy class."""

    def test_apply_edit_rewrite(self):
        """Test applying a REWRITE edit."""
        import logging
        import sys

        # Configure logging to output to stderr
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stderr,
        )
        logger = logging.getLogger(__name__)
        logger.info("Starting test_apply_edit_rewrite")

        strategy = DefaultEditStrategy()

        # Test case 1: Rewriting a phrase in the middle of a sentence
        original_text = "The system is design to learning from few examples."
        suggested_text = "The system is designed to learn from few examples."

        logger.debug(f"Test REWRITE - original_text: {original_text!r}")
        logger.debug(f"Test REWRITE - suggested_text: {suggested_text!r}")

        # Print the EditOperation values for debugging
        logger.debug(f"EditOperation.REWRITE value: {EditOperation.REWRITE!r}")
        logger.debug(f"EditOperation.REWRITE type: {type(EditOperation.REWRITE)!r}")
        logger.debug(
            f"EditOperation.REWRITE value.value: {EditOperation.REWRITE.value!r}"
        )

        suggestion1 = EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.CLARITY],
            original_text=original_text,
            suggested_text=suggested_text,
            confidence=0.95,
        )

        logger.debug(f"Test REWRITE - suggestion1 type: {type(suggestion1)}")
        logger.debug(f"Test REWRITE - suggestion1.operation: {suggestion1.operation!r}")
        logger.debug(
            f"Test REWRITE - suggestion1.operation type: {type(suggestion1.operation)!r}"
        )
        logger.debug(
            f"Test REWRITE - suggestion1.original_text: {suggestion1.original_text!r}"
        )
        logger.debug(
            f"Test REWRITE - suggestion1.original_text type: {type(suggestion1.original_text)!r}"
        )
        logger.debug(
            f"Test REWRITE - suggestion1.suggested_text: {suggestion1.suggested_text!r}"
        )
        logger.debug(
            f"Test REWRITE - suggestion1.suggested_text type: {type(suggestion1.suggested_text)!r}"
        )

        # Print the actual method being called
        import inspect

        logger.debug(f"Strategy class: {strategy.__class__.__name__}")
        logger.debug(
            f"Strategy class methods: {[m for m in dir(strategy.__class__) if not m.startswith('_')]}"
        )
        logger.debug(
            f"Strategy instance methods: {[m for m in dir(strategy) if not m.startswith('_')]}"
        )

        # Debug the method resolution
        import types

        method = getattr(strategy.__class__, "apply_edit", None)
        if method:
            logger.debug(f"Found apply_edit method: {method}")
            logger.debug(
                f"Method is function: {isinstance(method, types.FunctionType)}"
            )
            logger.debug(f"Method is method: {isinstance(method, types.MethodType)}")
            logger.debug(
                f"Method source: {inspect.getsource(method) if inspect.isfunction(method) else 'Not a function'}"
            )

        # REWRITE operation should replace the entire content with suggested_text
        print("\n=== DEBUG ===", file=sys.stderr)
        print(
            f"Before apply_edit - suggestion1.operation: {suggestion1.operation!r}",
            file=sys.stderr,
        )
        print(
            f"Before apply_edit - suggestion1.operation type: {type(suggestion1.operation)!r}",
            file=sys.stderr,
        )
        print(
            f"Before apply_edit - suggestion1.operation.value: {suggestion1.operation.value!r}",
            file=sys.stderr,
        )
        print(
            f"Before apply_edit - suggestion1.suggested_text: {suggestion1.suggested_text!r}",
            file=sys.stderr,
        )
        print(
            f"Before apply_edit - suggestion1.original_text: {suggestion1.original_text!r}",
            file=sys.stderr,
        )

        # Call the apply_edit method with the correct parameters
        print("\n=== DIRECT METHOD CALL ===", file=sys.stderr)
        print(
            "Calling strategy.apply_edit(original_text, suggestion1)", file=sys.stderr
        )
        print(f"strategy type: {type(strategy)}", file=sys.stderr)

        # Print the actual method that will be called
        bound_method = (
            strategy.apply_edit.__func__
            if hasattr(strategy.apply_edit, "__func__")
            else strategy.apply_edit
        )
        print(f"Method being called: {bound_method}", file=sys.stderr)
        print(
            f"Method source:\n{inspect.getsource(bound_method) if hasattr(bound_method, '__code__') else 'Cannot get source'}",
            file=sys.stderr,
        )

        # Try calling the method directly from the class
        result1 = DefaultEditStrategy.apply_edit(strategy, original_text, suggestion1)
        print(f"Direct class method call result: {result1!r}", file=sys.stderr)
        print(f"Result type: {type(result1)!r}", file=sys.stderr)
        print("=== END DIRECT METHOD CALL ===\n", file=sys.stderr)

        # Also try calling the instance method
        print("\n=== INSTANCE METHOD CALL ===", file=sys.stderr)
        instance_result = strategy.apply_edit(original_text, suggestion1)
        print(f"Instance method call result: {instance_result!r}", file=sys.stderr)
        print(f"Instance result type: {type(instance_result)!r}", file=sys.stderr)
        print("=== END INSTANCE METHOD CALL ===\n", file=sys.stderr)

        # Debug: Print the actual method being called
        logger.debug(f"Test REWRITE - result1: {result1!r}")
        logger.debug(f"Test REWRITE - result1 type: {type(result1)!r}")
        logger.debug(f"Test REWRITE - expected: {suggested_text!r}")
        logger.debug(f"Test REWRITE - expected type: {type(suggested_text)!r}")

        # Debug: Print the actual bytes to check for hidden characters
        logger.debug(f"Test REWRITE - result1 bytes: {list(result1.encode('utf-8'))}")
        logger.debug(
            f"Test REWRITE - expected bytes: {list(suggested_text.encode('utf-8'))}"
        )

        # Check if the strings are equal character by character
        for i, (r, e) in enumerate(zip(result1, suggested_text)):
            if r != e:
                logger.debug(
                    f"Mismatch at position {i}: result1[{i}]={r!r} ({ord(r)}) != expected[{i}]={e!r} ({ord(e)})"
                )
                break
        else:
            if len(result1) != len(suggested_text):
                logger.debug(
                    f"Length mismatch: result1 has {len(result1)} chars, expected has {len(suggested_text)} chars"
                )

        # Check if the method is being overridden by a mock or something
        import unittest.mock

        if isinstance(strategy.apply_edit, unittest.mock.Mock):
            logger.warning("apply_edit is a Mock object! This might be the issue.")

        # Final assertion
        assert (
            result1 == suggested_text
        ), f"Expected: {suggested_text!r}, got: {result1!r}"

        # Test case 2: Rewriting with empty original_text
        suggestion2 = EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.CLARITY],
            original_text="",
            suggested_text="New content",
            confidence=0.9,
        )
        result2 = strategy.apply_edit("Old content", suggestion2)
        assert result2 == "New content"

    def test_apply_edit_add(self):
        """Test applying an ADD edit."""
        strategy = DefaultEditStrategy()

        # Test adding text to the beginning of the content
        suggestion1 = EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.COMPLETENESS],
            original_text="",
            suggested_text="Please note: ",
            confidence=0.8,
        )
        result1 = strategy.apply_edit("This is a test", suggestion1)
        assert result1 == "Please note: This is a test"

        # Test adding text with original_text that exists in content
        suggestion2 = EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.COMPLETENESS],
            original_text="test",
            suggested_text="test [added info]",
            confidence=0.8,
        )
        result2 = strategy.apply_edit("This is a test", suggestion2)
        assert result2 == "This is a test [added info]"

    def test_apply_edit_remove(self):
        """Test applying a REMOVE edit."""
        strategy = DefaultEditStrategy()

        # Test removing text that exists in content
        original_text = "very very "
        content = "This is very very important"

        print("\n=== TEST DEBUGGING ===")
        print(
            f"Original text to remove: {original_text!r} (length: {len(original_text)})"
        )
        print(f"Content: {content!r} (length: {len(content)})")
        print(f"Original text in content: {original_text in content}")
        print(f"Content bytes: {content.encode('utf-8')}")
        print(f"Original text bytes: {original_text.encode('utf-8')}")

        # Try removing the text directly to verify
        expected = "This is important"
        direct_removal = content.replace(original_text, "", 1)
        print(
            f"Direct removal result: {direct_removal!r} (matches expected: {direct_removal == expected})"
        )

        suggestion1 = EditSuggestion(
            operation=EditOperation.REMOVE,
            criteria=[EditCriteria.READABILITY],
            original_text=original_text,
            suggested_text="",
            confidence=0.9,
        )

        print("\nCalling apply_edit...")
        result1 = strategy.apply_edit(content, suggestion1)
        print(f"\nResult from apply_edit: {result1!r}")
        print(f"Expected result: {expected!r}")
        print(f"Result matches expected: {result1 == expected}")
        print("=== END TEST DEBUGGING ===\n")

        assert result1 == expected

        # Test removing text that doesn't exist in content (should return original)
        suggestion2 = EditSuggestion(
            operation=EditOperation.REMOVE,
            criteria=[EditCriteria.READABILITY],
            original_text="nonexistent",
            suggested_text="",
            confidence=0.9,
        )
        result2 = strategy.apply_edit("This is a test", suggestion2)
        assert result2 == "This is a test"


class TestSelfEditor:
    """Tests for the SelfEditor class."""

    def test_initialization(self):
        """Test initializing SelfEditor with default parameters."""
        editor = SelfEditor()
        assert editor.auto_apply is False
        assert editor.min_confidence == 0.7
        assert editor.history_limit == 100
        assert isinstance(editor.strategy, DefaultEditStrategy)

    def test_evaluate_content_no_auto_apply(self):
        """Test evaluating content without auto-apply."""
        editor = SelfEditor(auto_apply=False)
        content = "This is a test"

        # Mock the strategy's evaluate method
        def mock_evaluate(content, **kwargs):
            return [
                EditSuggestion(
                    operation=EditOperation.ADD,
                    criteria=[EditCriteria.CLARITY],
                    original_text="",
                    suggested_text="Note: ",
                    confidence=0.8,
                )
            ]

        editor.strategy.evaluate = mock_evaluate

        suggestions = editor.evaluate_content(content, content_id="test_1")

        assert len(suggestions) == 1
        assert suggestions[0].operation == EditOperation.ADD
        assert "test_1" in editor.histories
        assert (
            editor.histories["test_1"].current_content == content
        )  # Should not change

    def test_evaluate_content_auto_apply(self):
        """Test evaluating content with auto-apply."""
        editor = SelfEditor(auto_apply=True, min_confidence=0.75)
        content = "This is a test"

        # Mock the strategy's evaluate method
        def mock_evaluate(content, **kwargs):
            return [
                EditSuggestion(
                    operation=EditOperation.ADD,
                    criteria=[EditCriteria.CLARITY],
                    original_text="",
                    suggested_text="Note: ",
                    confidence=0.8,  # Above threshold
                ),
                EditSuggestion(
                    operation=EditOperation.ADD,
                    criteria=[EditCriteria.CLARITY],
                    original_text="",
                    suggested_text=" (high importance)",
                    confidence=0.6,  # Below threshold
                ),
            ]

        editor.strategy.evaluate = mock_evaluate

        suggestions = editor.evaluate_content(content, content_id="test_2")

        # Only the low-confidence suggestion should be returned
        assert len(suggestions) == 1
        assert suggestions[0].confidence == 0.6

        # The high-confidence suggestion should have been prepended to the content
        assert editor.histories["test_2"].current_content == "Note: This is a test"

    def test_apply_edit(self):
        """Test applying an edit manually."""
        editor = SelfEditor()
        content = "Original content"

        # First evaluate to create history
        editor.evaluate_content(content, content_id="test_3")

        suggestion = EditSuggestion(
            operation=EditOperation.REPLACE,
            criteria=[EditCriteria.ACCURACY],
            original_text="Original",
            suggested_text="Updated",
            confidence=0.9,
        )

        result = editor.apply_edit("test_3", suggestion, apply=True)

        assert result == "Updated"
        assert editor.histories["test_3"].current_content == "Updated"
        assert len(editor.histories["test_3"].edit_history) == 1

    def test_get_edit_history(self):
        """Test retrieving edit history."""
        editor = SelfEditor()
        content = "Test content"

        # Create some history
        editor.evaluate_content(content, content_id="test_4")

        suggestion = EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.CLARITY],
            original_text="",
            suggested_text="Important: ",
            confidence=0.85,
        )

        editor.apply_edit("test_4", suggestion, apply=True)

        history = editor.get_edit_history("test_4")

        assert history is not None
        assert len(history.edit_history) == 1
        assert history.edit_history[0]["suggestion"]["operation"] == "add"

    def test_reset_content(self):
        """Test resetting content to its original state."""
        editor = SelfEditor()
        original_content = "Original content"

        # Create some history
        editor.evaluate_content(original_content, content_id="test_5")

        # Make some edits
        suggestion = EditSuggestion(
            operation=EditOperation.REPLACE,
            criteria=[EditCriteria.STYLE],
            original_text="Original",
            suggested_text="Modified",
            confidence=0.9,
        )

        editor.apply_edit("test_5", suggestion, apply=True)

        # Reset the content
        result = editor.reset_content("test_5")

        assert result == original_content
        assert editor.histories["test_5"].current_content == original_content
        assert len(editor.histories["test_5"].edit_history) == 0

    def test_history_limit(self):
        """Test that the history limit is enforced."""
        editor = SelfEditor(history_limit=2)

        # Create more histories than the limit
        for i in range(3):
            # Add a small delay to ensure different timestamps
            import time

            time.sleep(0.01)
            editor.evaluate_content(f"Content {i}", content_id=f"test_{i}")

        # The first history should have been removed
        assert "test_0" not in editor.histories
        assert "test_1" in editor.histories
        assert "test_2" in editor.histories
        assert len(editor.histories) == 2
