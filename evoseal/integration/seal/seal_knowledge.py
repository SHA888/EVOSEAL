"""
SEAL (Self-Adapting Language Models) Knowledge Integration
--------------------------
Integrates the KnowledgeBase with the SEAL (Self-Adapting Language Models) interface to provide
knowledge-enhanced language model interactions.
"""

from __future__ import annotations

from typing import Any

from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase, KnowledgeEntry


class SEALKnowledge:
    """
    Integrates KnowledgeBase with SEAL (Self-Adapting Language Models) to provide knowledge-enhanced interactions.

    This class provides methods to:
    1. Store and retrieve knowledge relevant to SEAL (Self-Adapting Language Models) operations
    2. Enhance prompts with relevant knowledge
    3. Learn from successful interactions
    """

    def __init__(
        self,
        knowledge_base: KnowledgeBase | None = None,
        storage_path: str = "knowledge_base.json",
    ):
        """Initialize with an optional KnowledgeBase instance.

        Args:
            knowledge_base: An optional KnowledgeBase instance. If not provided, a new one will be created.
            storage_path: Path to store the knowledge base. Only used if knowledge_base is not provided.
        """
        self.kb = (
            knowledge_base
            if knowledge_base is not None
            else KnowledgeBase(storage_path=storage_path)
        )

    def enhance_prompt(
        self,
        prompt: str,
        max_examples: int = 3,
        similarity_threshold: float = 0.3,
    ) -> str:
        """Enhance a prompt with relevant knowledge from the knowledge base.

        Args:
            prompt: The original prompt to enhance
            max_examples: Maximum number of knowledge entries to include
            similarity_threshold: Minimum similarity score to include an entry

        Returns:
            str: The enhanced prompt with relevant knowledge
        """
        # Search for relevant knowledge
        relevant_entries = self.kb.search_entries(query=prompt, limit=max_examples)

        if not relevant_entries:
            return prompt

        # Format the knowledge into the prompt
        knowledge_section = "\n\nRelevant Knowledge:\n"
        for i, entry in enumerate(relevant_entries, 1):
            knowledge_section += f"\n--- Knowledge {i} ---\n{entry.content}\n"
            if entry.metadata.get("source"):
                knowledge_section += f"Source: {entry.metadata['source']}\n"

        return f"{prompt}{knowledge_section}"

    def learn_from_interaction(
        self,
        prompt: str,
        response: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Store a successful interaction in the knowledge base.

        Args:
            prompt: The original prompt
            response: The successful response
            metadata: Optional metadata about the interaction
            tags: Optional tags for categorization

        Returns:
            str: The ID of the created knowledge entry
        """
        if metadata is None:
            metadata = {}
        if tags is None:
            tags = ["interaction"]

        # Create a structured knowledge entry
        knowledge_content = {
            "prompt": prompt,
            "response": response,
            "context": metadata.get("context", ""),
        }

        # Add source information if available
        if "source" not in metadata:
            metadata["source"] = "seal_interaction"

        # Store in knowledge base
        entry_id = self.kb.add_entry(content=knowledge_content, metadata=metadata, tags=tags)

        return entry_id

    def get_knowledge_for_task(
        self, task_description: str, max_entries: int = 5
    ) -> list[dict[str, Any]]:
        """Retrieve knowledge relevant to a specific task.

        Args:
            task_description: Description of the task
            max_entries: Maximum number of entries to return

        Returns:
            List of relevant knowledge entries as dictionaries
        """
        entries = self.kb.search_entries(query=task_description, limit=max_entries)

        return [
            {
                "id": entry.id,
                "content": entry.content,
                "metadata": entry.metadata,
                "tags": entry.tags,
            }
            for entry in entries
        ]

    def clear_knowledge(self) -> None:
        """Clear all knowledge from the knowledge base."""
        self.kb.clear()


# Example usage
if __name__ == "__main__":
    # Initialize with a file-based knowledge base
    seal_knowledge = SEALKnowledge(KnowledgeBase("seal_knowledge.json"))

    # Example of learning from an interaction
    entry_id = seal_knowledge.learn_from_interaction(
        prompt="How do I implement a binary search in Python?",
        response="Here's a Python implementation of binary search...",
        metadata={"difficulty": "easy", "language": "python"},
        tags=["algorithm", "python", "search"],
    )
    print(f"Stored knowledge with ID: {entry_id}")

    # Example of enhancing a prompt with knowledge
    enhanced = seal_knowledge.enhance_prompt("I need to implement a search algorithm in Python")
    print("\nEnhanced prompt:")
    print(enhanced)
