"""Unit tests for the CodeArchive model."""

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from evoseal.models.code_archive import (
    CodeArchive,
    CodeLanguage,
    CodeVisibility,
    create_code_archive,
)


def test_create_code_archive():
    """Test creating a basic code archive."""
    code = "print('Hello, World!')"
    title = "Hello World"
    author_id = "user123"

    archive = create_code_archive(
        content=code,
        language=CodeLanguage.PYTHON,
        title=title,
        author_id=author_id,
        description="A simple hello world program",
        tags=["test", "example"],
    )

    assert archive.content == code
    assert archive.language == CodeLanguage.PYTHON
    assert archive.title == title
    assert archive.author_id == author_id
    assert archive.description == "A simple hello world program"
    assert set(archive.tags) == {"test", "example"}
    assert archive.visibility == CodeVisibility.PRIVATE
    assert not archive.is_archived
    assert archive.version == "1.0.0"
    assert isinstance(archive.id, str)
    assert isinstance(archive.created_at, datetime)
    assert isinstance(archive.updated_at, datetime)


def test_code_archive_validation():
    """Test validation of required fields."""
    # Test empty content
    with pytest.raises(ValidationError) as exc_info:
        CodeArchive(content="", language=CodeLanguage.PYTHON, title="Test", author_id="user123")
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert "String should have at least 1 character" in str(errors[0]["msg"])

    # Test empty title
    with pytest.raises(ValidationError) as exc_info:
        create_code_archive(
            content="print('test')",
            language=CodeLanguage.PYTHON,
            title="",
            author_id="user123",
        )
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert "String should have at least 1 character" in str(errors[0]["msg"])


def test_code_archive_update():
    """Test updating a code archive."""
    # Store initial values for protected fields
    old_id = "test_id_123"
    old_created_at = datetime.now(timezone.utc) - timedelta(days=1)
    old_author_id = "user123"

    # Create with explicit timezone-aware datetime
    archive = create_code_archive(
        content="old content",
        language=CodeLanguage.PYTHON,
        title="Old Title",
        author_id=old_author_id,
        id=old_id,
        created_at=old_created_at,
        updated_at=old_created_at,  # Set initial updated_at
    )

    # Store the old updated_at as a timezone-aware datetime
    old_updated_at = archive.updated_at

    # Update some fields
    update_time = datetime.now(timezone.utc)
    archive.update(
        content="new content",
        title="New Title",
        description="Updated description",
        visibility=CodeVisibility.PUBLIC,
        # These should be ignored
        id="new_id",
        created_at=update_time,
        author_id="new_author",
    )

    # Verify updates
    assert archive.content == "new content"
    assert archive.title == "New Title"
    assert archive.description == "Updated description"
    assert archive.visibility == CodeVisibility.PUBLIC

    # Verify updated_at was updated and is timezone-aware
    assert archive.updated_at.tzinfo is not None
    assert archive.updated_at > old_updated_at

    # Verify protected fields weren't updated
    assert archive.id == old_id
    assert archive.created_at == old_created_at
    assert archive.author_id == old_author_id


def test_code_archive_tags():
    """Test tag management methods."""
    archive = create_code_archive(
        content="test",
        language=CodeLanguage.PYTHON,
        title="Test",
        author_id="user123",
    )

    # Add tags
    archive.add_tag("test")
    archive.add_tag("example")
    archive.add_tag("test")  # Duplicate should be ignored

    assert set(archive.tags) == {"test", "example"}

    # Remove tag
    assert archive.remove_tag("test") is True
    assert archive.tags == ["example"]

    # Remove non-existent tag
    assert archive.remove_tag("nonexistent") is False
    assert archive.tags == ["example"]


def test_code_archive_dependencies():
    """Test dependency management methods."""
    archive = create_code_archive(
        content="test",
        language=CodeLanguage.PYTHON,
        title="Test",
        author_id="user123",
    )

    # Add dependencies
    archive.add_dependency("requests>=2.25.0")
    archive.add_dependency("pydantic>=1.8.0")
    archive.add_dependency("requests>=2.25.0")  # Duplicate should be ignored

    assert set(archive.dependencies) == {"requests>=2.25.0", "pydantic>=1.8.0"}

    # Remove dependency
    assert archive.remove_dependency("pydantic>=1.8.0") is True
    assert archive.dependencies == ["requests>=2.25.0"]

    # Remove non-existent dependency
    assert archive.remove_dependency("nonexistent") is False
    assert archive.dependencies == ["requests>=2.25.0"]


def test_code_archive_archiving():
    """Test archive/unarchive functionality."""
    # Create with explicit timezone-aware datetime
    created_at = datetime.now(timezone.utc) - timedelta(days=1)
    archive = create_code_archive(
        content="test",
        language=CodeLanguage.PYTHON,
        title="Test",
        author_id="user123",
        created_at=created_at,
        updated_at=created_at,
    )

    assert not archive.is_archived

    # Archive
    old_updated_at = archive.updated_at
    archive.archive()

    assert archive.is_archived
    assert archive.updated_at > old_updated_at

    # Unarchive
    old_updated_at = archive.updated_at
    archive.unarchive()

    assert not archive.is_archived


def test_code_archive_fork():
    """Test forking a code archive."""
    # Create original with explicit timestamps
    original_created = datetime.now(timezone.utc) - timedelta(days=1)
    original_updated = datetime.now(timezone.utc) - timedelta(hours=1)

    original = create_code_archive(
        content="original content",
        language=CodeLanguage.PYTHON,
        title="Original",
        author_id="user1",
        description="Original description",
        tags=["original"],
        visibility=CodeVisibility.PUBLIC,
        created_at=original_created,
        updated_at=original_updated,
    )

    # Fork the archive
    fork_time = datetime.now(timezone.utc)
    fork = original.fork(
        new_author_id="user2",
        title="Forked Version",
        description="Forked description",
    )

    # Verify fork properties
    assert fork.id != original.id
    assert fork.parent_id == original.id
    assert fork.author_id == "user2"
    assert fork.title == "Forked Version"
    assert fork.description == "Forked description"
    assert fork.content == original.content
    assert fork.language == original.language
    assert fork.tags == original.tags
    assert fork.visibility == original.visibility
    assert fork.version == "1.0.0"  # Should be reset

    # Verify timestamps
    assert fork.created_at >= fork_time
    assert fork.updated_at >= fork_time
    assert fork.created_at > original.created_at
    assert fork.updated_at > original.updated_at


def test_code_archive_serialization():
    """Test serialization and deserialization."""
    # Create with explicit timestamps for consistent comparison
    created_at = datetime.now(timezone.utc) - timedelta(days=1)
    updated_at = datetime.now(timezone.utc)

    archive = create_code_archive(
        content="test",
        language=CodeLanguage.PYTHON,
        title="Test",
        author_id="user123",
        tags=["test"],
        metadata={"key": "value"},
        created_at=created_at,
        updated_at=updated_at,
    )

    # Convert to dict and back
    data = archive.model_dump()
    deserialized = CodeArchive.model_validate(data)

    # Compare individual fields to avoid timezone comparison issues
    assert deserialized.id == archive.id
    assert deserialized.content == archive.content
    assert deserialized.title == archive.title
    assert deserialized.author_id == archive.author_id
    assert deserialized.tags == archive.tags
    assert deserialized.metadata == archive.metadata
    assert deserialized.created_at == archive.created_at
    assert deserialized.updated_at == archive.updated_at

    # Test JSON serialization
    json_str = archive.model_dump_json()
    loaded = CodeArchive.model_validate_json(json_str)

    # Compare individual fields again
    assert loaded.id == archive.id
    assert loaded.content == archive.content
    assert loaded.title == archive.title
    assert loaded.author_id == archive.author_id
    assert loaded.tags == archive.tags
    assert loaded.metadata == archive.metadata
    assert loaded.created_at == archive.created_at
    assert loaded.updated_at == archive.updated_at


def test_create_code_archive_with_string_language():
    """Test creating a code archive with string language."""
    # Test with valid language string
    archive = create_code_archive(
        content="test",
        language="python",
        title="Test",
        author_id="user123",
    )
    assert archive.language == CodeLanguage.PYTHON

    # Test with unknown language string
    archive = create_code_archive(
        content="test",
        language="unknown_language",
        title="Test",
        author_id="user123",
    )
    assert archive.language == CodeLanguage.OTHER
