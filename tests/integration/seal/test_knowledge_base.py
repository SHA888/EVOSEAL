"""Tests for the KnowledgeBase class."""

from datetime import datetime
from pathlib import Path
from typing import Final

import pytest

from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase, KnowledgeEntry

# Test constants
EXPECTED_VERSION_AFTER_UPDATE: Final[int] = 2
EXPECTED_ENTRIES_AFTER_ADD: Final[int] = 2
EXPECTED_ENTRIES_AFTER_DELETE: Final[int] = 0
TAG_TEST_COUNT: Final[int] = 2
SEARCH_RESULT_COUNT: Final[int] = 1
TAG_SEARCH_COUNT: Final[int] = 2
ENTRY_VERSION_INITIAL: Final[int] = 1
ENTRY_VERSION_AFTER_UPDATE: Final[int] = 2
TEST_CONTENT: Final[str] = "Test content"
TEST_TAG: Final[str] = "test"


def test_knowledge_entry_creation():
    """Test creating a KnowledgeEntry."""
    entry = KnowledgeEntry(content="Test content")
    assert entry.content == "Test content"
    assert isinstance(entry.id, str)
    assert isinstance(entry.created_at, datetime)
    assert isinstance(entry.updated_at, datetime)
    assert entry.version == 1
    assert entry.tags == []


def test_knowledge_entry_update():
    """Test updating a KnowledgeEntry."""
    entry = KnowledgeEntry(content="Old content")
    old_updated_at = entry.updated_at

    entry.update("New content", {"source": "test"})

    assert entry.content == "New content"
    assert entry.metadata["source"] == "test"
    assert entry.version == EXPECTED_VERSION_AFTER_UPDATE
    assert entry.updated_at > old_updated_at


def test_knowledge_base_initialization(tmp_path):
    """Test initializing a KnowledgeBase."""
    storage_path = str(tmp_path / "test_kb_init.db")
    kb = KnowledgeBase(storage_path=storage_path)
    assert len(kb) == 0


def test_add_and_get_entry(tmp_path):
    """Test adding and retrieving an entry."""
    storage_path = str(tmp_path / "test_kb_add_get.db")
    kb = KnowledgeBase(storage_path=storage_path)
    entry_id = kb.add_entry(TEST_CONTENT, tags=[TEST_TAG])

    entry = kb.get_entry(entry_id)
    assert entry is not None
    assert entry.id is not None
    assert entry.content == TEST_CONTENT
    assert entry.version == ENTRY_VERSION_INITIAL
    assert TEST_TAG in entry.tags


def test_update_entry(tmp_path):
    """Test updating an entry."""
    storage_path = str(tmp_path / "test_kb_update.db")
    kb = KnowledgeBase(storage_path=storage_path)
    entry_id = kb.add_entry("Old content")

    updated = kb.update_entry(entry_id, "New content", {"source": "test"})
    assert updated is True

    entry = kb.get_entry(entry_id)
    assert entry.content == "New content"
    assert entry.metadata["source"] == "test"
    assert entry.version == ENTRY_VERSION_AFTER_UPDATE


def test_delete_entry(tmp_path):
    """Test deleting an entry."""
    storage_path = str(tmp_path / "test_kb_delete.db")
    kb = KnowledgeBase(storage_path=storage_path)
    entry_id = kb.add_entry("Test content")

    deleted = kb.delete_entry(entry_id)
    assert deleted is True
    assert kb.get_entry(entry_id) is None


def test_search_entries(tmp_path):
    """Test searching for entries."""
    storage_path = str(tmp_path / "test_kb_search.db")
    kb = KnowledgeBase(storage_path=storage_path)

    # Add test entries
    kb.add_entry("Python is a programming language", tags=["programming", "python"])
    kb.add_entry("Machine learning is a field of AI", tags=["ai", "machine-learning"])
    kb.add_entry("Python is used for data science", tags=["programming", "data-science"])

    # Search by tag
    results = kb.search_entries(tags=["programming"])
    assert len(results) == TAG_SEARCH_COUNT

    # Search by query
    results = kb.search_entries(query="machine learning")
    assert len(results) == SEARCH_RESULT_COUNT
    assert "Machine learning" in results[0].content

    # Search by metadata
    entry_id = kb.add_entry("Test entry", metadata={"source": "test"})
    results = kb.search_entries(metadata={"source": "test"})
    assert len(results) == SEARCH_RESULT_COUNT
    assert results[0].id == entry_id


def test_save_and_load(tmp_path: Path):
    """Test saving and loading the knowledge base."""
    # Create a temporary file
    db_path = tmp_path / "test_kb.json"

    # Create and populate a knowledge base
    kb1 = KnowledgeBase(db_path)
    kb1.add_entry("Test content 1", tags=["test"])
    kb1.add_entry("Test content 2", tags=["test", "example"])
    kb1.save_to_disk()

    # Load into a new knowledge base
    kb2 = KnowledgeBase(db_path)
    assert len(kb2) == EXPECTED_ENTRIES_AFTER_ADD

    # Verify content
    results = kb2.search_entries(tags=["test"])
    assert len(results) == EXPECTED_ENTRIES_AFTER_ADD
    assert any(entry.content == "Test content 1" for entry in results)
    assert any(entry.content == "Test content 2" for entry in results)


def test_add_remove_tags(tmp_path):
    """Test adding and removing tags from entries."""
    storage_path = str(tmp_path / "test_kb_tags.db")
    kb = KnowledgeBase(storage_path=storage_path)
    entry_id = kb.add_entry("Test content")

    # Add tags
    assert kb.add_tag(entry_id, TEST_TAG) is True
    assert kb.add_tag(entry_id, "example") is True

    entry = kb.get_entry(entry_id)
    assert len(entry.tags) == TAG_TEST_COUNT
    assert all(tag in entry.tags for tag in ["test", "example"])

    # Remove tag
    assert kb.remove_tag(entry_id, "test") is True
    entry = kb.get_entry(entry_id)
    assert entry.tags == ["example"]

    # Remove non-existent tag
    assert kb.remove_tag(entry_id, "nonexistent") is False


def test_clear(tmp_path):
    """Test clearing the knowledge base."""
    storage_path = str(tmp_path / "test_kb_clear.db")
    kb = KnowledgeBase(storage_path=storage_path)
    kb.add_entry("Test 1")
    kb.add_entry("Test 2")

    assert len(kb) == EXPECTED_ENTRIES_AFTER_ADD
    kb.clear()
    assert len(kb) == EXPECTED_ENTRIES_AFTER_DELETE


# ------------------------------------------------------------------
# Scored search / relevance score tests
# ------------------------------------------------------------------


def test_compute_relevance_score_exact_match():
    """Exact content match yields a high score."""
    score = KnowledgeBase._compute_relevance_score("python", "python")
    assert score == pytest.approx(1.0)


def test_compute_relevance_score_no_match():
    """No match yields 0.0."""
    score = KnowledgeBase._compute_relevance_score("python", "java is great")
    assert score == 0.0


def test_compute_relevance_score_case_insensitive():
    """Scoring is case-insensitive (caller must lowercase first)."""
    score = KnowledgeBase._compute_relevance_score("python", "PYTHON is great")
    assert score == 0.0  # Not lowered — caller's responsibility
    score_lower = KnowledgeBase._compute_relevance_score("python", "python is great")
    assert score_lower > 0.0


def test_compute_relevance_score_multiple_occurrences():
    """More occurrences yield a higher score."""
    single = KnowledgeBase._compute_relevance_score("ab", "ab cd ef")
    double = KnowledgeBase._compute_relevance_score("ab", "ab cd ab ef")
    assert double > single


def test_compute_relevance_score_partial():
    """Query appearing once in longer content yields a partial score."""
    score = KnowledgeBase._compute_relevance_score("python", "python is a programming language")
    assert 0.0 < score < 1.0


def test_compute_relevance_score_empty_content():
    """Empty content returns 0.0 without raising ZeroDivisionError."""
    assert KnowledgeBase._compute_relevance_score("python", "") == 0.0


def test_compute_relevance_score_empty_query():
    """Empty query returns 0.0 without raising ZeroDivisionError."""
    assert KnowledgeBase._compute_relevance_score("", "some content") == 0.0


def test_compute_relevance_score_both_empty():
    """Both empty returns 0.0 (no ZeroDivisionError from ''.count('')."""
    assert KnowledgeBase._compute_relevance_score("", "") == 0.0


def test_scored_search_returns_score_sorted(tmp_path):
    """_scored_search returns results sorted by score descending."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("Python is great")
    kb.add_entry("Python Python Python everywhere")
    kb.add_entry("Java is also fine")

    results = kb._scored_search("python", limit=10)
    assert len(results) == 2
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)
    # The entry with more "python" occurrences should rank higher
    assert results[0][0].content == "Python Python Python everywhere"


def test_scored_search_limit(tmp_path):
    """_scored_search respects the limit parameter."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    for i in range(5):
        kb.add_entry(f"Python example number {i}")

    results = kb._scored_search("python", limit=2)
    assert len(results) == 2


def test_scored_search_dict_content(tmp_path):
    """_scored_search works with dict content."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry({"concept": "Python", "desc": "A language"})
    kb.add_entry({"concept": "Java", "desc": "Another language"})

    results = kb._scored_search("python", limit=10)
    assert len(results) == 1
    assert results[0][1] > 0.0


@pytest.mark.asyncio
async def test_search_returns_real_scores(tmp_path):
    """search() returns varying scores, not hardcoded 1.0."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("Python is a great language")
    kb.add_entry("Python Python Python")

    results = await kb.search(query="python")
    assert len(results) == 2
    scores = [r["score"] for r in results]
    # Not all 1.0 — scores should differ based on occurrence density
    assert scores[0] > scores[1]
    assert all(0.0 < s <= 1.0 for s in scores)


@pytest.mark.asyncio
async def test_search_min_score_filters(tmp_path):
    """search(min_score=...) filters out low-scoring results."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("Python is a great programming language for data science")
    kb.add_entry("Python Python Python Python Python")

    # Without min_score, both match
    all_results = await kb.search(query="python")
    assert len(all_results) == 2

    # With a high min_score, only the high-scoring one passes
    high_score = all_results[0]["score"]
    filtered = await kb.search(query="python", min_score=high_score)
    assert len(filtered) == 1
    assert filtered[0]["content"] == "Python Python Python Python Python"


@pytest.mark.asyncio
async def test_search_min_score_none_returns_all(tmp_path):
    """search(min_score=None) returns all matches without filtering."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("Python is great")
    kb.add_entry("Java is also fine")

    results = await kb.search(query="python", min_score=None)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_negative_max_results_raises(tmp_path):
    """search(max_results=-1) raises ValueError."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("hello")
    with pytest.raises(ValueError, match="max_results must be non-negative"):
        await kb.search(query="hello", max_results=-1)


@pytest.mark.asyncio
async def test_search_max_results_zero_returns_empty(tmp_path):
    """search(max_results=0) returns empty list."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("hello")
    results = await kb.search(query="hello", max_results=0)
    assert results == []


@pytest.mark.asyncio
async def test_search_no_match_returns_empty(tmp_path):
    """search() with no matching entries returns empty list."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("Python is great")
    results = await kb.search(query="nonexistent")
    assert results == []


@pytest.mark.asyncio
async def test_search_result_format(tmp_path):
    """search() result dicts have expected keys and types."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("Python is great", tags=["programming"], metadata={"source": "test"})
    results = await kb.search(query="python")
    assert len(results) == 1
    r = results[0]
    assert "id" in r and isinstance(r["id"], str)
    assert "content" in r
    assert "score" in r and isinstance(r["score"], float)
    assert "metadata" in r and r["metadata"] == {"source": "test"}
    assert "tags" in r and "programming" in r["tags"]
    assert "created_at" in r
    assert "updated_at" in r


@pytest.mark.asyncio
async def test_search_none_query_raises(tmp_path):
    """search(query=None) raises ValueError, not AttributeError."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("hello")
    with pytest.raises(ValueError, match="query must be a non-empty string"):
        await kb.search(query=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_search_empty_query_raises(tmp_path):
    """search(query='') raises ValueError."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("hello")
    with pytest.raises(ValueError, match="query must be a non-empty string"):
        await kb.search(query="")


@pytest.mark.asyncio
async def test_search_int_query_raises(tmp_path):
    """search(query=42) raises ValueError, not AttributeError."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry("hello")
    with pytest.raises(ValueError, match="query must be a non-empty string"):
        await kb.search(query=42)  # type: ignore[arg-type]


def test_flatten_content_nested_dict():
    """_flatten_content recurses into nested dicts."""
    content = {"name": "Python", "details": {"version": 3.12, "typed": True}}
    result = KnowledgeBase._flatten_content(content)
    assert "Python" in result
    assert "3.12" in result
    # bool should be excluded
    assert "True" not in result


def test_flatten_content_lists_and_tuples():
    """_flatten_content recurses into lists and tuples."""
    content = {"tags": ["python", "ml"], "versions": (3.10, 3.11)}
    result = KnowledgeBase._flatten_content(content)
    assert "python" in result
    assert "ml" in result
    assert "3.1" in result
    assert "3.11" in result


def test_flatten_content_excludes_bool():
    """_flatten_content does not include bool values."""
    content = {"active": True, "deleted": False, "name": "test"}
    result = KnowledgeBase._flatten_content(content)
    assert "True" not in result
    assert "False" not in result
    assert "test" in result


def test_scored_search_nested_content(tmp_path):
    """_scored_search finds terms in nested list values."""
    kb = KnowledgeBase(str(tmp_path / "kb.db"))
    kb.add_entry({"tags": ["python", "ml"], "desc": "Machine learning"})
    results = kb._scored_search("python", limit=10)
    assert len(results) == 1
    assert results[0][1] > 0.0
