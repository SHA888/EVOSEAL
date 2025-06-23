"""
KnowledgeBase module for the SEAL system.

This module provides the KnowledgeBase class for structured storage and retrieval
of knowledge in the SEAL system.
"""

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    """Represents a single entry in the knowledge base."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    tags: List[str] = Field(default_factory=list)

    def update(self, new_content: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
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
    
    def __init__(self, storage_path: str):
        """Initialize the knowledge base with a storage path."""
        self.storage_path = storage_path
        self.entries: Dict[str, KnowledgeEntry] = {}
        self._lock = Lock()
        self._file_lock = Lock()  # For file operations
        self._initialize_storage()
    
    def _initialize_storage(self) -> None:
        """Initialize storage by loading from disk if path exists."""
        if self.storage_path and os.path.exists(self.storage_path):
            self.load_from_disk(self.storage_path)
    
    def add_entry(
        self,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        entry_id: Optional[str] = None
    ) -> str:
        """Add a new entry to the knowledge base in a thread-safe manner."""
        with self._lock:  # Use lock for thread safety
            entry = KnowledgeEntry(
                id=entry_id or str(uuid4()),
                content=content,
                metadata=metadata or {},
                tags=tags or []
            )
            self.entries[entry.id] = entry
            self._save_to_disk()
            return entry.id
    
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
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
        new_content: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update an existing entry.
        
        Args:
            entry_id: The ID of the entry to update.
            new_content: New content for the entry. If None, only metadata will be updated.
            metadata: New metadata to merge with existing metadata.
            
        Returns:
            bool: True if the entry was updated, False if not found.
        """
        if entry_id not in self.entries:
            return False
            
        entry = self.entries[entry_id]
        
        if new_content is not None:
            entry.update(new_content, metadata)
        elif metadata is not None:
            entry.metadata.update(metadata)
            entry.updated_at = datetime.now(timezone.utc)
        
        self._save_to_disk()
        return True
    
    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry from the knowledge base.
        
        Args:
            entry_id: The ID of the entry to delete.
            
        Returns:
            bool: True if the entry was deleted, False if not found.
        """
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save_to_disk()
            return True
        return False
    
    def search_entries(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[KnowledgeEntry]:
        """Search for entries matching the given criteria.
        
        Args:
            query: Optional text query to search in entry content.
            tags: Optional list of tags to filter by.
            metadata: Optional metadata key-value pairs to filter by.
            limit: Maximum number of results to return.
            
        Returns:
            List[KnowledgeEntry]: List of matching entries.
        """
        results = list(self.entries.values())
        
        # Filter by tags if provided
        if tags:
            results = [entry for entry in results if any(tag in entry.tags for tag in tags)]
        
        # Filter by metadata if provided
        if metadata:
            for key, value in metadata.items():
                results = [entry for entry in results 
                          if key in entry.metadata and entry.metadata[key] == value]
        
        # Simple text search in content if query provided
        if query:
            query = query.lower()
            results = [
                entry for entry in results
                if (isinstance(entry.content, str) and query in entry.content.lower()) or
                   (isinstance(entry.content, dict) and 
                    any(query in str(v).lower() for v in entry.content.values()
                        if isinstance(v, (str, int, float))))
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
    
    def save_to_disk(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save the knowledge base to disk.
        
        Args:
            path: Optional path to save to. If not provided, uses the storage_path
                  provided at initialization.
        """
        save_path = str(path) if path is not None else self.storage_path
        if not save_path:
            raise ValueError("No storage path provided")
            
        with self._file_lock:
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                
                # Use exclusive lock for writing
                with open(save_path, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
                    try:
                        data = {
                            'entries': [
                                entry.model_dump()
                                for entry in self.entries.values()
                            ]
                        }
                        json.dump(data, f, indent=2, default=str)
                        f.flush()
                        os.fsync(f.fileno())  # Ensure data is written to disk
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
            except Exception as e:
                raise RuntimeError(f"Failed to save knowledge base: {e}")
    
    def load_from_disk(self, path: Union[str, Path]) -> None:
        """Load the knowledge base from disk.
        
        Args:
            path: Path to the knowledge base file.
        """
        path = str(path)
        if not os.path.exists(path):
            return
            
        with self._file_lock:
            try:
                with open(path, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                    try:
                        data = json.load(f)
                        entries = {}
                        for entry_data in data.get('entries', []):
                            # Handle datetime deserialization
                            if 'created_at' in entry_data and isinstance(entry_data['created_at'], str):
                                entry_data['created_at'] = datetime.fromisoformat(entry_data['created_at'])
                            if 'updated_at' in entry_data and isinstance(entry_data['updated_at'], str):
                                entry_data['updated_at'] = datetime.fromisoformat(entry_data['updated_at'])
                            
                            entry = KnowledgeEntry(**entry_data)
                            entries[entry.id] = entry
                        
                        # Update entries in a thread-safe way
                        with self._lock:
                            self.entries = entries
                    except json.JSONDecodeError:
                        # If file is empty or corrupted, start with empty knowledge base
                        with self._lock:
                            self.entries = {}
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
            except FileNotFoundError:
                # File was deleted between existence check and opening
                with self._lock:
                    self.entries = {}
            except Exception as e:
                raise RuntimeError(f"Failed to load knowledge base: {e}")
    
    def _save_to_disk(self) -> None:
        """Internal method to save to the default storage path if configured."""
        if self.storage_path:
            self.save_to_disk()
    
    def clear(self) -> None:
        """Clear all entries from the knowledge base."""
        with self._lock:
            self.entries.clear()
            self._save_to_disk()
    
    def __len__(self) -> int:
        """Return the number of entries in the knowledge base."""
        with self._lock:
            return len(self.entries)
    
    def get_all_entries(self) -> List[KnowledgeEntry]:
        """Get all entries in the knowledge base.
        
        Returns:
            List[KnowledgeEntry]: List of all entries.
        """
        with self._lock:
            return list(self.entries.values())


# Example usage
if __name__ == "__main__":
    # Create a knowledge base with file-based storage
    kb = KnowledgeBase("knowledge_base.json")
    
    # Add some entries
    entry1_id = kb.add_entry(
        "Python is a high-level programming language.",
        tags=["programming", "python"]
    )
    
    entry2_id = kb.add_entry(
        {"concept": "Machine Learning", "description": "A field of AI that uses statistical techniques."},
        tags=["ai", "machine-learning"]
    )
    
    # Search for entries
    results = kb.search_entries(query="python")
    print(f"Found {len(results)} entries matching 'python'")
    
    # Update an entry
    kb.update_entry(entry1_id, "Python is a high-level, interpreted programming language.")
    
    # Save to disk (happens automatically when using methods that modify the KB)
    kb.save_to_disk()
