"""
Mock implementation of KnowledgeBase for testing purposes.
"""

from __future__ import annotations

from typing import Any


class MockKnowledgeBase:
    """Mock implementation of KnowledgeBase for testing.

    Provides the same async ``search`` interface as the real
    :class:`KnowledgeBase` so that callers like
    :class:`EnhancedSEALSystem` can ``await`` the result without
    crashing.
    """

    def __init__(self, storage_path: str | None = None):
        """Initialize the mock knowledge base."""
        self.storage_path = storage_path

    async def search(
        self,
        query: str,
        max_results: int | None = None,
        min_score: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Mock async search matching the KnowledgeBase.search signature.

        Parameters
        ----------
        query:
            Free-text query to match against mock content.
        max_results:
            Maximum number of results.  Defaults to 5.
        min_score:
            Minimum relevance score (inclusive).  Defaults to 0.3.
        context:
            Accepted for API compatibility; not used.
        """
        # Intentionally synchronous body — no real I/O; async is for
        # interface compatibility with the real KnowledgeBase.search().
        limit = max_results if max_results is not None else 5
        threshold = min_score if min_score is not None else 0.3

        # Simple keyword matching for demonstration
        query_lower = query.lower()

        # Mock knowledge items
        knowledge_items = [
            {
                "id": "kb1",
                "content": "Paris is the capital of France.",
                "score": 0.95 if "france" in query_lower and "capital" in query_lower else 0.5,
                "metadata": {"source": "general_knowledge"},
            },
            {
                "id": "kb2",
                "content": "The Eiffel Tower is located in Paris, France.",
                "score": 0.8 if "france" in query_lower else 0.4,
                "metadata": {"source": "general_knowledge"},
            },
            {
                "id": "kb3",
                "content": "France is a country in Western Europe.",
                "score": 0.7 if "france" in query_lower else 0.3,
                "metadata": {"source": "general_knowledge"},
            },
        ]

        # Filter by minimum score and sort by score (highest first)
        filtered = [item for item in knowledge_items if item["score"] >= threshold]
        filtered.sort(key=lambda x: x["score"], reverse=True)

        return filtered[:limit]

    def add_document(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Mock implementation of add_document."""
        # In a real implementation, this would add a document to the knowledge base
        doc_id = f"doc_{len(self._get_mock_documents()) + 1}"
        return doc_id

    def _get_mock_documents(self) -> list[dict[str, Any]]:
        """Helper method to get mock documents."""
        return []  # Not implemented in mock
