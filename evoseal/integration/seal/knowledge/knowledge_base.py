"""
KnowledgeBase module for the SEAL system.

This module provides the KnowledgeBase class for structured storage and retrieval
of knowledge in the SEAL system.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    """Represents a single entry in the knowledge base."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    tags: List[str] = Field(default_factory=list)

    def update(self, new_content: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update the entry with new content and metadata."""
        self.content = new_content
        if metadata is not None:
            self.metadata.update(metadata)
        self.updated_at = datetime.utcnow()
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
    
    def __init__(self, storage_path: Optional[Union[str, Path]] = None):
        """Initialize the KnowledgeBase.
        
        Args:
            storage_path: Optional path to persist the knowledge base.
                         If None, the knowledge base will be in-memory only.
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.entries: Dict[str, KnowledgeEntry] = {}
        self._initialize_storage()
    
    def _initialize_storage(self) -> None:
        """Initialize storage by loading from disk if path exists."""
        if self.storage_path and self.storage_path.exists():
            self.load_from_disk(self.storage_path)
    
    def add_entry(
        self,
        content: Any,
        entry_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """Add a new entry to the knowledge base.
        
        Args:
            content: The content to store (can be any JSON-serializable object)
            entry_id: Optional ID for the entry. If not provided, a UUID will be generated.
            metadata: Optional metadata for the entry.
            tags: Optional list of tags for the entry.
            
        Returns:
            str: The ID of the created entry.
        """
        if metadata is None:
            metadata = {}
        if tags is None:
            tags = []
            
        entry = KnowledgeEntry(
            id=entry_id or str(uuid4()),
            content=content,
            metadata=metadata,
            tags=tags
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
            entry.updated_at = datetime.utcnow()
        
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
            self.entries[entry_id].updated_at = datetime.utcnow()
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
            self.entries[entry_id].updated_at = datetime.utcnow()
            self._save_to_disk()
            return True
        return False
    
    def save_to_disk(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save the knowledge base to disk.
        
        Args:
            path: Optional path to save to. If not provided, uses the storage_path
                  provided at initialization.
        """
        if path is None and self.storage_path is None:
            raise ValueError("No storage path provided")
            
        save_path = Path(path) if path else self.storage_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'entries': [entry.model_dump() for entry in self.entries.values()]
        }
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str, indent=2)
    
    def load_from_disk(self, path: Union[str, Path]) -> None:
        """Load the knowledge base from disk.
        
        Args:
            path: Path to the knowledge base file.
        """
        path = Path(path)
        if not path.exists():
            return
            
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.entries = {}
        for entry_data in data.get('entries', []):
            # Handle datetime deserialization
            if 'created_at' in entry_data and isinstance(entry_data['created_at'], str):
                entry_data['created_at'] = datetime.fromisoformat(entry_data['created_at'])
            if 'updated_at' in entry_data and isinstance(entry_data['updated_at'], str):
                entry_data['updated_at'] = datetime.fromisoformat(entry_data['updated_at'])
            
            entry = KnowledgeEntry(**entry_data)
            self.entries[entry.id] = entry
    
    def _save_to_disk(self) -> None:
        """Internal method to save to the default storage path if configured."""
        if self.storage_path:
            self.save_to_disk()
    
    def clear(self) -> None:
        """Clear all entries from the knowledge base."""
        self.entries.clear()
        self._save_to_disk()
    
    def __len__(self) -> int:
        """Return the number of entries in the knowledge base."""
        return len(self.entries)
    
    def get_all_entries(self) -> List[KnowledgeEntry]:
        """Get all entries in the knowledge base.
        
        Returns:
            List[KnowledgeEntry]: List of all entries.
        """
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
