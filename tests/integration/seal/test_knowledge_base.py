"""Tests for the KnowledgeBase class."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase, KnowledgeEntry


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
    assert entry.version == 2
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
    entry_id = kb.add_entry("Test content", tags=["test"])
    
    entry = kb.get_entry(entry_id)
    assert entry is not None
    assert entry.content == "Test content"
    assert "test" in entry.tags


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
    assert entry.version == 2


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
    assert len(results) == 2
    
    # Search by query
    results = kb.search_entries(query="machine learning")
    assert len(results) == 1
    assert "Machine learning" in results[0].content
    
    # Search by metadata
    entry_id = kb.add_entry("Test entry", metadata={"source": "test"})
    results = kb.search_entries(metadata={"source": "test"})
    assert len(results) == 1
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
    assert len(kb2) == 2
    
    # Verify content
    results = kb2.search_entries(tags=["test"])
    assert len(results) == 2
    assert any(entry.content == "Test content 1" for entry in results)
    assert any(entry.content == "Test content 2" for entry in results)


def test_add_remove_tags(tmp_path):
    """Test adding and removing tags from entries."""
    storage_path = str(tmp_path / "test_kb_tags.db")
    kb = KnowledgeBase(storage_path=storage_path)
    entry_id = kb.add_entry("Test content")
    
    # Add tags
    assert kb.add_tag(entry_id, "test") is True
    assert kb.add_tag(entry_id, "example") is True
    
    entry = kb.get_entry(entry_id)
    assert set(entry.tags) == {"test", "example"}
    
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
    
    assert len(kb) == 2
    kb.clear()
    assert len(kb) == 0
