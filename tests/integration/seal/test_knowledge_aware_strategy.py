"""Tests for the KnowledgeAwareStrategy class."""

from unittest.mock import MagicMock, create_autospec, patch

import pytest

from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase
from evoseal.integration.seal.self_editor import (
    DefaultEditStrategy,
    EditCriteria,
    EditOperation,
    EditSuggestion,
    KnowledgeAwareStrategy,
)


class TestKnowledgeAwareStrategy:
    """Tests for the KnowledgeAwareStrategy class."""

    @pytest.fixture
    def mock_knowledge_base(self):
        """Create a mock KnowledgeBase instance."""
        kb = MagicMock(spec=KnowledgeBase)
        kb.search_entries.return_value = [
            {"content": "This is a relevant context from the knowledge base."}
        ]
        return kb

    def test_initialization(self, mock_knowledge_base):
        """Test initializing KnowledgeAwareStrategy."""
        strategy = KnowledgeAwareStrategy(
            knowledge_base=mock_knowledge_base,
            min_similarity=0.5,
            max_context_entries=5,
        )

        assert strategy.knowledge_base == mock_knowledge_base
        assert strategy.min_similarity == 0.5
        assert strategy.max_context_entries == 5

    def test_get_relevant_context(self, mock_knowledge_base):
        """Test retrieving relevant context from knowledge base."""
        strategy = KnowledgeAwareStrategy(mock_knowledge_base)
        content = "Test content to find context for"

        context = strategy.get_relevant_context(content)

        mock_knowledge_base.search_entries.assert_called_once_with(
            query=content, limit=strategy.max_context_entries
        )
        assert len(context) == 1
        assert "content" in context[0]

    def test_evaluate_with_context(self, mock_knowledge_base):
        """Test evaluate method with context from knowledge base."""
        # Setup mock return values
        mock_suggestions = [
            EditSuggestion(
                operation=EditOperation.REWRITE,
                criteria=[EditCriteria.CLARITY],
                original_text="test",
                suggested_text="improved test",
                confidence=0.8,
            )
        ]

        # Create a mock DefaultEditStrategy
        mock_strategy = create_autospec(DefaultEditStrategy, instance=True)
        mock_strategy.evaluate.return_value = mock_suggestions

        # Patch the DefaultEditStrategy to return our mock
        with patch(
            "evoseal.integration.seal.self_editor.strategies.knowledge_aware_strategy.DefaultEditStrategy",
            return_value=mock_strategy,
        ):
            strategy = KnowledgeAwareStrategy(mock_knowledge_base)
            content = "Test content to evaluate"

            suggestions = strategy.evaluate(content)

            # Verify knowledge base was queried
            mock_knowledge_base.search_entries.assert_called_once()

            # Verify default strategy was used
            mock_strategy.evaluate.assert_called_once_with(content)

            # Verify suggestions were returned
            assert suggestions == mock_suggestions

    def test_apply_edit(self, mock_knowledge_base):
        """Test applying an edit using the strategy."""
        # Create a mock DefaultEditStrategy
        mock_strategy = create_autospec(DefaultEditStrategy, instance=True)
        mock_strategy.apply_edit.return_value = "Edited content"

        # Patch the DefaultEditStrategy to return our mock
        with patch(
            "evoseal.integration.seal.self_editor.strategies.knowledge_aware_strategy.DefaultEditStrategy",
            return_value=mock_strategy,
        ):
            strategy = KnowledgeAwareStrategy(mock_knowledge_base)
            content = "Original content"
            suggestion = EditSuggestion(
                operation=EditOperation.REPLACE,
                criteria=[EditCriteria.CLARITY],
                original_text="Original",
                suggested_text="Edited",
                confidence=0.9,
            )

            result = strategy.apply_edit(content, suggestion)

            # Verify default strategy was used
            mock_strategy.apply_edit.assert_called_once_with(content, suggestion)
            assert result == "Edited content"

    def test_min_similarity_validation(self, mock_knowledge_base):
        """Test validation of min_similarity parameter."""
        # Test invalid values
        with pytest.raises(
            ValueError, match="min_similarity must be between 0.0 and 1.0"
        ):
            KnowledgeAwareStrategy(mock_knowledge_base, min_similarity=-0.1)

        with pytest.raises(
            ValueError, match="min_similarity must be between 0.0 and 1.0"
        ):
            KnowledgeAwareStrategy(mock_knowledge_base, min_similarity=1.1)

        # Test valid values (should not raise)
        KnowledgeAwareStrategy(mock_knowledge_base, min_similarity=0.0)
        KnowledgeAwareStrategy(mock_knowledge_base, min_similarity=0.5)
        KnowledgeAwareStrategy(mock_knowledge_base, min_similarity=1.0)
