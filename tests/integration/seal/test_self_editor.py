"""Tests for the SelfEditor component."""

import pytest
from datetime import datetime

from evoseal.integration.seal.self_editor import (
    SelfEditor,
    EditSuggestion,
    EditOperation,
    EditCriteria,
    EditHistory,
    DefaultEditStrategy,
)


class TestEditSuggestion:
    """Tests for the EditSuggestion class."""
    
    def test_edit_suggestion_creation(self):
        """Test creating an EditSuggestion instance."""
        suggestion = EditSuggestion(
            operation=EditOperation.REPLACE,
            criteria=[EditCriteria.GRAMMAR, EditCriteria.CLARITY],
            original_text="is design to",
            suggested_text="is designed to",
            confidence=0.9,
            explanation="Correct verb form"
        )
        
        assert suggestion.operation == EditOperation.REPLACE
        assert EditCriteria.GRAMMAR in suggestion.criteria
        assert EditCriteria.CLARITY in suggestion.criteria
        assert suggestion.original_text == "is design to"
        assert suggestion.suggested_text == "is designed to"
        assert suggestion.confidence == 0.9
        assert suggestion.explanation == "Correct verb form"
    
    def test_to_dict(self):
        """Test converting EditSuggestion to dictionary."""
        suggestion = EditSuggestion(
            operation=EditOperation.REPLACE,
            criteria=[EditCriteria.GRAMMAR],
            original_text="is design to",
            suggested_text="is designed to",
            confidence=0.9,
        )
        
        data = suggestion.to_dict()
        assert data["operation"] == "replace"
        assert data["criteria"] == ["grammar"]
        assert data["original_text"] == "is design to"
        assert data["suggested_text"] == "is designed to"
        assert data["confidence"] == 0.9
    
    def test_from_dict(self):
        """Test creating EditSuggestion from dictionary."""
        data = {
            "operation": "replace",
            "criteria": ["grammar"],
            "original_text": "is design to",
            "suggested_text": "is designed to",
            "confidence": 0.9,
            "explanation": "Test"
        }
        
        suggestion = EditSuggestion.from_dict(data)
        assert suggestion.operation == EditOperation.REPLACE
        assert suggestion.criteria == [EditCriteria.GRAMMAR]
        assert suggestion.original_text == "is design to"
        assert suggestion.suggested_text == "is designed to"
        assert suggestion.confidence == 0.9
        assert suggestion.explanation == "Test"


class TestEditHistory:
    """Tests for the EditHistory class."""
    
    def test_add_edit(self):
        """Test adding an edit to the history."""
        history = EditHistory(
            content_id="test_1",
            original_content="Original content",
            current_content="Current content"
        )
        
        suggestion = EditSuggestion(
            operation=EditOperation.REPLACE,
            criteria=[EditCriteria.GRAMMAR],
            original_text="Original",
            suggested_text="Updated",
            confidence=0.9
        )
        
        history.add_edit(suggestion, applied=True)
        
        assert len(history.edit_history) == 1
        assert history.current_content == "Updated"  # Should only contain the updated text, not the full content
        assert history.updated_at > history.created_at
    
    def test_add_edit_not_applied(self):
        """Test adding an edit that is not applied."""
        history = EditHistory(
            content_id="test_1",
            original_content="Original content",
            current_content="Current content"
        )
        
        suggestion = EditSuggestion(
            operation=EditOperation.REPLACE,
            criteria=[EditCriteria.GRAMMAR],
            original_text="Original",
            suggested_text="Updated",
            confidence=0.9
        )
        
        history.add_edit(suggestion, applied=False)
        
        assert len(history.edit_history) == 1
        assert history.current_content == "Current content"  # Should not change


class TestDefaultEditStrategy:
    """Tests for the DefaultEditStrategy class."""
    
    def test_apply_edit_replace(self):
        """Test applying a REPLACE edit."""
        strategy = DefaultEditStrategy()
        suggestion = EditSuggestion(
            operation=EditOperation.REPLACE,
            criteria=[EditCriteria.GRAMMAR],
            original_text="is design to",
            suggested_text="is designed to",
            confidence=0.9
        )
        
        result = strategy.apply_edit("This is design to test", suggestion)
        assert result == "This is designed to test"
    
    def test_apply_edit_add(self):
        """Test applying an ADD edit."""
        strategy = DefaultEditStrategy()
        suggestion = EditSuggestion(
            operation=EditOperation.ADD,
            criteria=[EditCriteria.CLARITY],
            original_text="",
            suggested_text="Please note: ",
            confidence=0.8
        )
        
        result = strategy.apply_edit("This is a test", suggestion)
        assert result == "This is a test Please note: "
    
    def test_apply_edit_remove(self):
        """Test applying a REMOVE edit."""
        strategy = DefaultEditStrategy()
        suggestion = EditSuggestion(
            operation=EditOperation.REMOVE,
            criteria=[EditCriteria.CONCISENESS],
            original_text="very very ",
            suggested_text="",
            confidence=0.9
        )
        
        result = strategy.apply_edit("This is very very important", suggestion)
        assert result == "This is important"
    
    def test_apply_edit_rewrite(self):
        """Test applying a REWRITE edit."""
        strategy = DefaultEditStrategy()
        suggestion = EditSuggestion(
            operation=EditOperation.REWRITE,
            criteria=[EditCriteria.CLARITY],
            original_text="The system is design to learning from few examples.",
            suggested_text="The system is designed to learn from few examples.",
            confidence=0.95
        )
        
        result = strategy.apply_edit("The system is design to learning from few examples.", suggestion)
        assert result == "The system is designed to learn from few examples."


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
                    confidence=0.8
                )
            ]
        
        editor.strategy.evaluate = mock_evaluate
        
        suggestions = editor.evaluate_content(content, content_id="test_1")
        
        assert len(suggestions) == 1
        assert suggestions[0].operation == EditOperation.ADD
        assert "test_1" in editor.histories
        assert editor.histories["test_1"].current_content == content  # Should not change
    
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
                    confidence=0.8  # Above threshold
                ),
                EditSuggestion(
                    operation=EditOperation.ADD,
                    criteria=[EditCriteria.CLARITY],
                    original_text="",
                    suggested_text=" (high importance)",
                    confidence=0.6  # Below threshold
                )
            ]
        
        editor.strategy.evaluate = mock_evaluate
        
        suggestions = editor.evaluate_content(content, content_id="test_2")
        
        # Only the low-confidence suggestion should be returned
        assert len(suggestions) == 1
        assert suggestions[0].confidence == 0.6
        
        # The high-confidence suggestion should have been applied at the end
        assert editor.histories["test_2"].current_content == "This is a test Note: "
    
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
            confidence=0.9
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
            confidence=0.85
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
            confidence=0.9
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
