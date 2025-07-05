"""
KnowledgeBase module for the SEAL system.

This module provides the KnowledgeBase class for structured storage and retrieval
of knowledge in the SEAL system.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    """Represents a single entry in the knowledge base."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: Any
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    tags: list[str] = Field(default_factory=list)

    def update(self, new_content: Any, metadata: dict[str, Any] | None = None) -> None:
        """Update the entry with new content and metadata."""
        self.content = new_content
        if metadata is not None:
            self.metadata.update(metadata)
        self.updated_at = datetime.now(timezone.utc)
        self.version += 1


class KnowledgeBase:
    """
    A knowledge base for storing and retrieving structured knowledge.

    The KnowledgeBase provides methods for:
    1. Storing knowledge in a structured format
    2. Efficiently retrieving knowledge using various query methods
    3. Supporting different knowledge formats (text, structured data)
    4. Versioning of knowledge entries
    5. Persistence to disk
    """

    # Constants for timeouts and retries
    DEFAULT_LOCK_TIMEOUT = 5  # seconds
    SAVE_LOCK_TIMEOUT = 2  # seconds
    MAX_RETRIES = 3
    DEFAULT_SEARCH_LIMIT = 10
    RETRY_BACKOFF_BASE = 0.1  # seconds
    SAVE_RETRY_BACKOFF_BASE = 0.2  # seconds
    JSON_INDENT = 2

    def __init__(self, storage_path: str):
        """Initialize the knowledge base with a storage path."""
        self.storage_path = storage_path
        self.entries: dict[str, KnowledgeEntry] = {}
        # Use RLock instead of Lock to allow reentrant locking
        self._lock = RLock()  # For in-memory operations
        self._file_lock = RLock()  # For file operations
        self._initialized = False
        self._initialize_storage()
        self._initialized = True

    def _initialize_storage(self) -> None:
        """Initialize storage by loading from disk if path exists."""
        if self.storage_path and os.path.exists(self.storage_path):
            self.load_from_disk(self.storage_path)

    def add_entry(
        self,
        content: Any,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        entry_id: str | None = None,
    ) -> str:
        """Add a new entry to the knowledge base in a thread-safe manner."""
        # Create the entry object outside the lock
        new_entry = KnowledgeEntry(
            id=entry_id or str(uuid4()),
            content=content,
            metadata=metadata or {},
            tags=tags or [],
        )

        # Acquire lock with timeout to prevent deadlocks
        if not self._lock.acquire(timeout=5):  # 5-second timeout
            print("WARNING: Could not acquire lock for adding entry, proceeding without lock")
            # If we can't get the lock, still add the entry but without synchronization
            self.entries[new_entry.id] = new_entry
        else:
            try:
                # Add entry to in-memory dictionary
                self.entries[new_entry.id] = new_entry
            finally:
                self._lock.release()

        # Save to disk after modifying the entries
        try:
            self._save_to_disk()
        except Exception as e:
            print(f"Warning: Failed to save to disk after adding entry: {e}")
            # Continue despite save failure - entry is still in memory

        return new_entry.id

    def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        """Retrieve an entry by its ID.

        Args:
            entry_id: The ID of the entry to retrieve.

        Returns:
            Optional[KnowledgeEntry]: The entry if found, None otherwise.
        """
        return self.entries.get(entry_id)

    def update_entry(
        self,
        entry_id: str,
        new_content: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update an existing entry.

        Args:
            entry_id: The ID of the entry to update.
            new_content: New content for the entry. If None, only metadata will be updated.
            metadata: New metadata to merge with existing metadata.

        Returns:
            bool: True if the entry was updated, False if not found.
        """
        updated = False
        entry_to_update = None

        # First check if entry exists without holding the lock
        if entry_id not in self.entries:
            return False

        # Try to acquire lock with timeout
        if not self._lock.acquire(timeout=5):  # 5-second timeout
            print("WARNING: Could not acquire lock for updating entry, proceeding without lock")
            # If we can't get the lock, try to update anyway
            if entry_id in self.entries:
                entry_to_update = self.entries[entry_id]
        else:
            try:
                if entry_id in self.entries:
                    entry_to_update = self.entries[entry_id]
            finally:
                self._lock.release()

        # If we found the entry, update it
        if entry_to_update:
            if new_content is not None:
                entry_to_update.update(new_content, metadata)
                updated = True
            elif metadata is not None:
                entry_to_update.metadata.update(metadata)
                entry_to_update.updated_at = datetime.now(timezone.utc)
                updated = True

        # Only save if we actually updated something
        if updated:
            try:
                self._save_to_disk()
            except Exception as e:
                print(f"Warning: Failed to save to disk after updating entry: {e}")
                # Continue despite save failure - entry is still updated in memory

        return updated

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry from the knowledge base.

        Args:
            entry_id: The ID of the entry to delete.

        Returns:
            bool: True if the entry was deleted, False if not found.
        """
        deleted = False

        with self._lock:
            if entry_id not in self.entries:
                return False

            del self.entries[entry_id]
            deleted = True

        # Save outside the lock to reduce lock contention
        if deleted:
            self._save_to_disk()

        return True

    def search_entries(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[KnowledgeEntry]:
        """Search for entries matching the given criteria.

        Args:
            query: Optional text query to search in entry content.
            tags: Optional list of tags to filter by.
            metadata: Optional metadata key-value pairs to filter by.
            limit: Maximum number of results to return.

        Returns:
            list[KnowledgeEntry]: List of matching entries.
        """
        # Use default limit if None is provided
        if limit is None:
            limit = self.DEFAULT_SEARCH_LIMIT
        results = list(self.entries.values())

        # Filter by tags if provided
        if tags:
            results = [entry for entry in results if any(tag in entry.tags for tag in tags)]

        # Filter by metadata if provided
        if metadata:
            for key, value in metadata.items():
                results = [
                    entry
                    for entry in results
                    if key in entry.metadata and entry.metadata[key] == value
                ]

        # Simple text search in content if query provided
        if query:
            query = query.lower()
            results = [
                entry
                for entry in results
                if (isinstance(entry.content, str) and query in entry.content.lower())
                or (
                    isinstance(entry.content, dict)
                    and any(
                        query in str(v).lower()
                        for v in entry.content.values()
                        if isinstance(v, (str, int, float))
                    )
                )
            ]

        # Sort by last updated (newest first)
        results.sort(key=lambda x: x.updated_at, reverse=True)

        return results[:limit]

    def add_tag(self, entry_id: str, tag: str) -> bool:
        """Add a tag to an entry.

        Args:
            entry_id: The ID of the entry.
            tag: The tag to add.

        Returns:
            bool: True if the tag was added, False if the entry doesn't exist.
        """
        if entry_id not in self.entries:
            return False

        if tag not in self.entries[entry_id].tags:
            self.entries[entry_id].tags.append(tag)
            self.entries[entry_id].updated_at = datetime.now(timezone.utc)
            self._save_to_disk()
        return True

    def remove_tag(self, entry_id: str, tag: str) -> bool:
        """Remove a tag from an entry.

        Args:
            entry_id: The ID of the entry.
            tag: The tag to remove.

        Returns:
            bool: True if the tag was removed, False otherwise.
        """
        if entry_id not in self.entries:
            return False

        if tag in self.entries[entry_id].tags:
            self.entries[entry_id].tags.remove(tag)
            self.entries[entry_id].updated_at = datetime.now(timezone.utc)
            self._save_to_disk()
            return True
        return False

    def save_to_disk(self, path: str | Path | None = None) -> None:
        """Save the knowledge base to disk.

        Args:
            path: Optional path to save to. If not provided, uses the storage_path
                  provided at initialization.
        """
        save_path = str(path) if path is not None else self.storage_path
        if not save_path:
            raise ValueError("No storage path provided")

        # Create a snapshot without holding the lock for too long
        entries_snapshot = {}
        try:
            # Use a non-blocking lock acquisition with timeout
            if self._lock.acquire(timeout=self.SAVE_LOCK_TIMEOUT):
                try:
                    # Create a deep copy of entries to avoid race conditions during serialization
                    for entry_id, entry in self.entries.items():
                        entries_snapshot[entry_id] = entry.model_copy(deep=True)
                finally:
                    self._lock.release()
            else:
                # If we couldn't get the lock, log a warning and continue with empty snapshot
                print("WARNING: Could not acquire lock for reading entries, using empty snapshot")
        except Exception as e:
            print(f"Error acquiring lock: {e}")
            # Continue with whatever entries we have

        # Then perform file operations
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)

            # Use exclusive lock for writing, but with a timeout
            with open(save_path, "w") as f:
                # Use non-blocking lock with retry
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        # Try to get a non-blocking lock
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        try:
                            data = {
                                "entries": [
                                    entry.model_dump() for entry in entries_snapshot.values()
                                ]
                            }
                            json.dump(data, f, indent=self.JSON_INDENT, default=str)
                            f.flush()  # Flush to OS buffer
                            os.fsync(f.fileno())  # Force OS to write to disk
                            break  # Successfully wrote data, exit retry loop
                        finally:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
                    except OSError as e:
                        if retry < max_retries - 1:
                            # Wait a bit before retrying
                            time.sleep(self.RETRY_BACKOFF_BASE * (retry + 1))
                        else:
                            # On last retry, raise the exception
                            raise RuntimeError(
                                f"Could not acquire file lock after {max_retries} retries"
                            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to save knowledge base: {e}") from e

    def load_from_disk(self, path: str | Path) -> None:
        """Load the knowledge base from disk.

        Args:
            path: Path to the knowledge base file.
        """
        path = str(path)
        if not os.path.exists(path):
            with self._lock:
                self.entries = {}
            return

        f = None
        try:
            f = open(path, encoding="utf-8")
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading

            try:
                data = json.load(f)
                entries = {}
                for entry_data in data.get("entries", []):
                    # Handle datetime deserialization
                    if "created_at" in entry_data and isinstance(entry_data["created_at"], str):
                        entry_data["created_at"] = datetime.fromisoformat(entry_data["created_at"])
                    if "updated_at" in entry_data and isinstance(entry_data["updated_at"], str):
                        entry_data["updated_at"] = datetime.fromisoformat(entry_data["updated_at"])

                    entry = KnowledgeEntry(**entry_data)
                    entries[entry.id] = entry

                with self._lock:
                    self.entries = entries

            except json.JSONDecodeError:
                # If file is empty or corrupted, start with empty knowledge base
                with self._lock:
                    self.entries = {}

        except FileNotFoundError:
            # File was deleted between existence check and opening
            with self._lock:
                self.entries = {}

        except Exception as e:
            raise RuntimeError(f"Failed to load knowledge base: {e}") from e

        finally:
            if f is not None:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    f.close()
                except (OSError, IOError) as close_error:
                    # Debug log instead of silent pass
                    import logging

                    logging.getLogger(__name__).debug(
                        f"Error closing file: {close_error}", exc_info=True
                    )

    def _save_to_disk(self) -> None:
        """Internal method to save to the default storage path if configured."""
        if self.storage_path:
            try:
                # Use the public method with a maximum of 3 retries
                max_retries = 3
                last_error = None

                for retry in range(max_retries):
                    try:
                        self.save_to_disk(self.storage_path)
                        return  # Success, exit the method
                    except Exception as e:
                        last_error = e
                        # Wait a bit before retrying
                        time.sleep(self.SAVE_RETRY_BACKOFF_BASE * (retry + 1))

                # If we get here, all retries failed
                print(f"Warning: Failed to save to disk after {max_retries} retries: {last_error}")
            except Exception as e:
                print(f"Error in _save_to_disk: {e}")
                # Continue execution despite the error

    def clear(self) -> None:
        """Clear all entries from the knowledge base."""
        with self._lock:
            self.entries.clear()
            self._save_to_disk()

    def __len__(self) -> int:
        """Return the number of entries in the knowledge base."""
        with self._lock:
            return len(self.entries)

    def get_all_entries(self) -> list[KnowledgeEntry]:
        """Get all entries in the knowledge base.

        Returns:
            list[KnowledgeEntry]: List of all entries.
        """
        with self._lock:
            return list(self.entries.values())


# Example usage
if __name__ == "__main__":
    # Create a knowledge base with file-based storage
    kb = KnowledgeBase("knowledge_base.json")

    # Add some entries
    entry1_id = kb.add_entry(
        "Python is a high-level programming language.", tags=["programming", "python"]
    )

    entry2_id = kb.add_entry(
        {
            "concept": "Machine Learning",
            "description": "A field of AI that uses statistical techniques.",
        },
        tags=["ai", "machine-learning"],
    )

    # Search for entries
    results = kb.search_entries(query="python")
    print(f"Found {len(results)} entries matching 'python'")

    # Update an entry
    kb.update_entry(entry1_id, "Python is a high-level, interpreted programming language.")

    # Save to disk (happens automatically when using methods that modify the KB)
    kb.save_to_disk()
