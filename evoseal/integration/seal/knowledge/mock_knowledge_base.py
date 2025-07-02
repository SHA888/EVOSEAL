"""
Mock implementation of KnowledgeBase for testing purposes.
"""

from typing import Any, Dict, List, Optional


class MockKnowledgeBase:
    """Mock implementation of KnowledgeBase for testing."""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize the mock knowledge base."""
        self.storage_path = storage_path

    def search(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        min_score: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Mock implementation of search."""
        # Simple keyword matching for demonstration
        query = query.lower()

        # Mock knowledge items
        knowledge_items = [
            {
                "id": "kb1",
                "content": "Paris is the capital of France.",
                "score": 0.95 if "france" in query and "capital" in query else 0.5,
                "metadata": {"source": "general_knowledge"},
            },
            {
                "id": "kb2",
                "content": "The Eiffel Tower is located in Paris, France.",
                "score": 0.8 if "france" in query else 0.4,
                "metadata": {"source": "general_knowledge"},
            },
            {
                "id": "kb3",
                "content": "France is a country in Western Europe.",
                "score": 0.7 if "france" in query else 0.3,
                "metadata": {"source": "general_knowledge"},
            },
        ]

        # Filter by minimum score and sort by score (highest first)
        filtered = [item for item in knowledge_items if item["score"] >= min_score]
        filtered.sort(key=lambda x: x["score"], reverse=True)

        # Apply limit
        return filtered[:limit]

    def add_document(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Mock implementation of add_document."""
        # In a real implementation, this would add a document to the knowledge base
        doc_id = f"doc_{len(self._get_mock_documents()) + 1}"
        return doc_id

    def _get_mock_documents(self) -> List[Dict[str, Any]]:
        """Helper method to get mock documents."""
        return []  # Not implemented in mock
