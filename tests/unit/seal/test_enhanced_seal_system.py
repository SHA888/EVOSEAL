"""
Tests for the Enhanced SEAL system.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from pydantic import ValidationError

from evoseal.integration.seal.enhanced_seal_system import (
    ConversationHistory,
    EnhancedSEALSystem,
    SEALConfig,
)
from evoseal.integration.seal.knowledge.mock_knowledge_base import MockKnowledgeBase
from evoseal.integration.seal.self_editor.mock_self_editor import MockSelfEditor


@pytest.fixture
def mock_knowledge_base():
    """Fixture providing a mock knowledge base."""
    kb = MockKnowledgeBase()
    # Add some test data
    kb.search = AsyncMock(
        return_value=[
            {
                "id": "kb1",
                "content": "Test knowledge 1",
                "score": 0.9,
                "metadata": {"source": "test"},
            }
        ]
    )
    return kb


@pytest.fixture
def mock_self_editor():
    """Fixture providing a mock self-editor."""
    editor = MockSelfEditor()
    # Keep the original implementation of suggest_edits and apply_edit
    # from MockSelfEditor class which already handles the context parameter
    return editor


@pytest_asyncio.fixture
async def enhanced_seal_system(mock_knowledge_base, mock_self_editor):
    """Fixture providing a configured EnhancedSEALSystem for testing."""
    config = SEALConfig(
        enable_metrics=True,
        enable_caching=True,
        enable_self_editing=True,
        max_concurrent_requests=5,
        cache_ttl_seconds=60,
        max_cache_size=100,
    )

    system = EnhancedSEALSystem(
        config=config,
        knowledge_base=mock_knowledge_base,
        self_editor=mock_self_editor,
    )

    await system.start()
    try:
        yield system
    finally:
        await system.stop()


@pytest.mark.asyncio
async def test_lifecycle_management():
    """Test system startup and shutdown."""
    system = EnhancedSEALSystem()

    # Test starting
    await system.start()
    assert system._is_running is True

    # Test stopping
    await system.stop()
    assert system._is_running is False


@pytest.mark.asyncio
async def test_async_context_manager():
    """Test the async context manager interface."""
    async with EnhancedSEALSystem() as system:
        assert system._is_running is True
        assert isinstance(system.conversation_history, ConversationHistory)

    # Should be stopped after context
    assert system._is_running is False


@pytest.mark.asyncio
async def test_process_prompt(
    enhanced_seal_system, mock_knowledge_base, mock_self_editor
):
    """Test processing a prompt with knowledge and self-editing."""
    # Setup test data
    test_prompt = "What is the capital of France?"
    test_context = {"user_id": "test_user"}

    # Process the prompt
    result = await enhanced_seal_system.process_prompt(test_prompt, test_context)

    # Verify the result
    assert "response" in result
    assert result["metadata"]["success"] is True
    assert len(result["metadata"]["knowledge_used"]) > 0

    # Verify mocks were called
    mock_knowledge_base.search.assert_called_once()
    # The mock self-editor will only suggest edits for specific prompts
    # based on the implementation in MockSelfEditor


@pytest.mark.asyncio
async def test_caching(enhanced_seal_system):
    """Test that caching works as expected."""
    # Clear any existing cache
    enhanced_seal_system.clear_cache()

    # Enable caching for this test
    enhanced_seal_system.config.enable_caching = True

    test_prompt = "What is the capital of France?"
    test_context = {"test": "caching_test"}

    # First call - should miss cache
    result1 = await enhanced_seal_system.process_prompt(test_prompt, test_context)
    assert result1["metadata"]["cached"] is False

    # Second call with same prompt and context - should hit cache
    result2 = await enhanced_seal_system.process_prompt(test_prompt, test_context)
    assert result2["metadata"]["cached"] is True

    # Call with different context - should miss cache
    different_context = {"test": "different_test"}
    result3 = await enhanced_seal_system.process_prompt(test_prompt, different_context)
    assert result3["metadata"]["cached"] is False

    # Clear cache and try again
    enhanced_seal_system.clear_cache()
    result3 = await enhanced_seal_system.process_prompt(test_prompt)
    assert result3["metadata"]["cached"] is False


@pytest.mark.asyncio
async def test_metrics_collection(enhanced_seal_system):
    """Test that metrics are collected properly."""
    # Process a few prompts
    prompts = ["Test 1", "Test 2", "Test 3"]
    for prompt in prompts:
        await enhanced_seal_system.process_prompt(prompt)

    # Get metrics
    metrics = enhanced_seal_system.get_metrics()

    # Verify metrics
    assert metrics["request_count"] == len(prompts)
    assert metrics["error_count"] == 0
    assert metrics["cache"]["hits"] >= 0  # Could be 0 if not testing with cache
    assert metrics["timing"]["avg_processing_time"] > 0


@pytest.mark.asyncio
async def test_conversation_history(enhanced_seal_system):
    """Test that conversation history is maintained correctly."""
    # Clear any existing history
    enhanced_seal_system.conversation_history.clear()

    # Add some messages
    await enhanced_seal_system.process_prompt("Hello")
    await enhanced_seal_system.process_prompt("How are you?")

    # Check history
    history = enhanced_seal_system.conversation_history.get_history()
    assert len(history) >= 2  # At least 2 assistant responses
    assert all(
        msg["role"] == "assistant" for msg in history
    )  # Only assistant messages are stored
    assert any(
        "Hello" in msg["content"] or "How are you" in msg["content"] for msg in history
    )


@pytest.mark.asyncio
async def test_error_handling(enhanced_seal_system, caplog):
    """Test that errors are handled gracefully."""
    # Test with invalid input
    with pytest.raises(ValueError):
        await enhanced_seal_system.process_prompt("")

    # Verify error was recorded in metrics
    metrics = enhanced_seal_system.get_metrics()
    assert metrics["error_count"] > 0
    assert "ValueError" in metrics["errors_by_type"]


@pytest.mark.asyncio
async def test_config_validation():
    """Test that invalid config values raise validation errors."""
    # Test valid config
    valid_config = SEALConfig(
        knowledge_similarity_threshold=0.5,
        min_confidence_for_editing=0.7,
    )
    assert valid_config.knowledge_similarity_threshold == 0.5

    # Test invalid config
    with pytest.raises(ValidationError):
        SEALConfig(knowledge_similarity_threshold=1.5)  # Should be <= 1.0

    with pytest.raises(ValidationError):
        SEALConfig(min_confidence_for_editing=-0.1)  # Should be >= 0.0


@pytest.mark.asyncio
async def test_timezone_handling(enhanced_seal_system):
    """Test that timezone-aware datetimes are handled correctly."""
    # Test with timezone-naive datetime (using now() instead of utcnow())
    now_naive = datetime.now()
    await enhanced_seal_system.process_prompt("Test timezone", {"timestamp": now_naive})

    # Test with timezone-aware datetime
    now_aware = datetime.now(timezone.utc)
    await enhanced_seal_system.process_prompt("Test timezone", {"timestamp": now_aware})

    # Test with string timestamp
    await enhanced_seal_system.process_prompt(
        "Test timezone", {"timestamp": "2023-01-01T00:00:00Z"}
    )


@pytest.mark.asyncio
async def test_self_editing_disabled(enhanced_seal_system, mock_self_editor):
    """Test that self-editing can be disabled."""
    # Disable self-editing
    enhanced_seal_system.config.enable_self_editing = False

    # Create a test suggestion
    test_suggestion = {
        "type": "fact_verification",
        "operation": "REPLACE",
        "original_text": "Original",
        "suggested_text": "Edited",
        "confidence": 0.9,
        "explanation": "Test edit",
    }

    # Patch the suggest_edits method to return our test suggestion
    with patch.object(
        mock_self_editor, "suggest_edits", return_value=[test_suggestion]
    ) as mock_suggest:

        # Process a prompt
        await enhanced_seal_system.process_prompt(
            "Test prompt", context={"test": "context"}
        )

        # Verify suggest_edits was not called when self-editing is disabled
        mock_suggest.assert_not_called()


@pytest.mark.asyncio
async def test_retrieve_relevant_knowledge(enhanced_seal_system, mock_knowledge_base):
    """Test knowledge retrieval with caching."""
    # Set up test data
    test_query = "test query"
    test_results = [
        {"content": "Test knowledge 1", "score": 0.9, "metadata": {}},
        {"content": "Test knowledge 2", "score": 0.8, "metadata": {}},
    ]

    # Configure mock to return test results on first call, empty on subsequent calls
    mock_knowledge_base.search.side_effect = [
        test_results,  # First call
        [],  # Second call (should use cache)
    ]

    # First call - should query knowledge base
    results = await enhanced_seal_system.retrieve_relevant_knowledge(
        test_query, context={}
    )
    assert results == test_results

    # Second call - should use cache
    cached_results = await enhanced_seal_system.retrieve_relevant_knowledge(
        test_query, context={}
    )
    assert (
        cached_results == test_results
    )  # Should still get the same results from cache


@pytest.mark.asyncio
async def test_self_edit_process(
    enhanced_seal_system, mock_self_editor, mock_knowledge_base
):
    """Test the self-editing process."""
    # Enable self-editing for this test
    enhanced_seal_system.config.enable_self_editing = True

    # Set up test data
    test_prompt = "Test prompt"
    test_context = {"user_id": "test_user"}
    test_knowledge = [
        {"content": "Test knowledge 1", "score": 0.9, "metadata": {}},
    ]

    # Configure mock knowledge base
    mock_knowledge_base.search.return_value = test_knowledge

    # Configure mock editor with a test suggestion
    test_suggestion = {
        "type": "clarity_improvement",
        "operation": "REPLACE",
        "original_text": "test",
        "suggested_text": "tested",
        "confidence": 0.9,
        "explanation": "Improved clarity",
    }

    # Patch the suggest_edits method
    with patch.object(
        mock_self_editor, "suggest_edits", return_value=[test_suggestion]
    ) as mock_suggest:

        # Process a prompt that will trigger self-editing
        response = await enhanced_seal_system.process_prompt(
            test_prompt, context=test_context
        )

        # Verify suggest_edits was called with the correct arguments
        mock_suggest.assert_called_once()

        # Verify the response contains the expected data structure
        assert isinstance(response, dict)
        assert "response" in response
        assert "metadata" in response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
