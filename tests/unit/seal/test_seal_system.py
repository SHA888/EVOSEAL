"""
Tests for the SEAL system integration.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase
from evoseal.integration.seal.seal_system import SEALConfig, SEALSystem
from evoseal.integration.seal.self_editor import SelfEditor
from evoseal.integration.seal.self_editor.self_editor import EditOperation, EditSuggestion


class MockKnowledgeBase:
    """Mock KnowledgeBase for testing."""

    def __init__(self):
        self.search_results = []
        self.added_items = []

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.search_results[:limit]

    async def add(self, content: Any, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        item = {"content": content, "metadata": metadata or {}, **kwargs}
        self.added_items.append(item)
        return "mock_id"


class MockSelfEditor:
    """Mock SelfEditor for testing."""

    def __init__(self):
        self.suggestions = []
        self.applied_edits = []

    async def evaluate_content(
        self, content: str, content_id: Optional[str] = None, **kwargs
    ) -> List[EditSuggestion]:
        return self.suggestions

    async def apply_edit(
        self, content_id: str, suggestion: EditSuggestion, apply: bool = True
    ) -> str:
        self.applied_edits.append((content_id, suggestion, apply))
        if apply and suggestion.operation == EditOperation.REPLACE:
            return suggestion.suggested_text
        return suggestion.original_text


@pytest.fixture
def mock_knowledge_base():
    return MockKnowledgeBase()


@pytest.fixture
def mock_self_editor():
    return MockSelfEditor()


@pytest.fixture
def seal_system(mock_knowledge_base, mock_self_editor):
    with (
        patch('evoseal.integration.seal.seal_system.KnowledgeAwareStrategy') as mock_strategy,
        patch('evoseal.integration.seal.seal_system.SelfEditor') as mock_self_editor_cls,
    ):

        # Configure mocks
        mock_strategy.return_value = MagicMock()
        mock_self_editor_cls.return_value = mock_self_editor

        # Create system with test config
        config = SEALConfig(auto_apply_edits=True, min_confidence=0.7, max_knowledge_items=3)

        system = SEALSystem(knowledge_base=mock_knowledge_base, config=config)

        # Replace the actual editor with our mock
        system.self_editor = mock_self_editor

        return system, mock_knowledge_base, mock_self_editor


@pytest.mark.asyncio
async def test_process_prompt_basic(seal_system):
    """Test basic prompt processing."""
    system, mock_kb, mock_editor = seal_system

    # Configure mock knowledge
    mock_kb.search_results = [
        {"content": "Paris is the capital of France.", "score": 0.9, "metadata": {}},
        {"content": "France is a country in Europe.", "score": 0.8, "metadata": {}},
    ]

    # Configure mock editor
    mock_editor.suggestions = [
        EditSuggestion(
            operation=EditOperation.REPLACE,
            criteria=[],
            original_text="[RESPONSE TO: What is the capital of France?]",
            suggested_text="The capital of France is Paris.",
            confidence=0.9,
            explanation="Improved response with direct answer.",
        )
    ]

    # Process prompt
    response = await system.process_prompt(
        "What is the capital of France?", context={"user_id": "test_user"}
    )

    # Verify response
    assert "Paris" in response
    assert len(mock_editor.applied_edits) == 1

    # Verify knowledge base was queried
    assert len(mock_kb.search_results) > 0


@pytest.mark.asyncio
async def test_self_editing_disabled(seal_system):
    """Test that self-editing can be disabled."""
    system, mock_kb, mock_editor = seal_system
    system.config.enable_self_editing = False

    # Process prompt
    response = await system.process_prompt("Test prompt")

    # Verify no edits were applied
    assert len(mock_editor.applied_edits) == 0


@pytest.mark.asyncio
async def test_retrieve_relevant_knowledge(seal_system):
    """Test knowledge retrieval with caching."""
    system, mock_kb, _ = seal_system

    # Set up test data
    test_query = "test query"
    test_results = [
        {"content": "Test result 1", "score": 0.9, "metadata": {}},
        {"content": "Test result 2", "score": 0.8, "metadata": {}},
    ]
    mock_kb.search_results = test_results

    # First call - should query knowledge base
    results = await system.retrieve_relevant_knowledge(test_query)
    assert results == test_results

    # Second call - should use cache
    mock_kb.search_results = []  # Empty results to verify cache is used
    cached_results = await system.retrieve_relevant_knowledge(test_query)
    assert cached_results == test_results


@pytest.mark.asyncio
async def test_self_edit_process(seal_system):
    """Test the self-editing process."""
    system, _, mock_editor = seal_system

    # Set up test data
    original_content = "Original content"
    edited_content = "Edited content"

    # Configure mock editor
    mock_editor.suggestions = [
        EditSuggestion(
            operation=EditOperation.REPLACE,
            criteria=[],
            original_text=original_content,
            suggested_text=edited_content,
            confidence=0.9,
            explanation="Test edit",
        )
    ]

    # Apply self-edit
    result = await system.self_edit(content=original_content, context={"test": "context"})

    # Verify edit was applied
    assert result == edited_content
    assert len(mock_editor.applied_edits) == 1

    # Verify edit was applied with correct parameters
    content_id, suggestion, apply = mock_editor.applied_edits[0]
    assert content_id == "default"  # Default content ID when not specified
    assert suggestion.suggested_text == edited_content
    assert apply is True


@pytest.mark.asyncio
async def test_error_handling(seal_system, caplog):
    """Test that errors are properly handled."""
    system, mock_kb, _ = seal_system

    # Make knowledge base raise an error
    async def mock_search(*args, **kwargs):
        raise ValueError("Test error")

    mock_kb.search = mock_search

    # Process should handle the error gracefully
    with caplog.at_level(logging.WARNING):
        response = await system.process_prompt("Test prompt")

    # Should still return a response
    assert response == "[RESPONSE TO: Test prompt]"

    # Should log the warning
    assert "Error retrieving knowledge" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
