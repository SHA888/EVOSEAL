# KnowledgeBase Component

The KnowledgeBase component provides structured storage and retrieval of knowledge for the SEAL system. It's designed to be flexible, efficient, and easy to integrate with other components.

## Features

- **Structured Storage**: Store knowledge entries with content, metadata, and tags
- **Efficient Retrieval**: Search by content, tags, and metadata
- **Versioning**: Automatic version tracking for entries
- **Persistence**: Save and load knowledge to/from disk
- **Integration**: Seamless integration with SEAL interface

## Usage

### Basic Usage

```python
from evoseal.integration.seal.knowledge import KnowledgeBase

# Initialize with file-based storage
kb = KnowledgeBase("knowledge_base.json")

# Add an entry
entry_id = kb.add_entry(
    "Python is a high-level programming language.",
    tags=["programming", "python"]
)

# Retrieve an entry
entry = kb.get_entry(entry_id)
print(entry.content)

# Search for entries
results = kb.search_entries(query="python")
for result in results:
    print(f"- {result.content}")
```

### Integration with SEAL

The `SEALKnowledge` class provides a higher-level interface for integrating the KnowledgeBase with SEAL:

```python
from evoseal.integration.seal.seal_knowledge import SEALKnowledge, KnowledgeBase

# Initialize
seal_kb = SEALKnowledge(KnowledgeBase("seal_knowledge.json"))

# Learn from an interaction
seal_kb.learn_from_interaction(
    prompt="How to implement quicksort in Python?",
    response="Here's a Python implementation of quicksort...",
    tags=["algorithm", "python", "sorting"]
)

# Enhance a prompt with relevant knowledge
enhanced_prompt = seal_kb.enhance_prompt(
    "I need to implement a sorting algorithm in Python"
)
print(enhanced_prompt)
```

## API Reference

### KnowledgeBase

```python
class KnowledgeBase:
    def __init__(self, storage_path: Optional[Union[str, Path]] = None)
    def add_entry(self, content: Any, entry_id: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 tags: Optional[List[str]] = None) -> str
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]
    def update_entry(self, entry_id: str,
                    new_content: Optional[Any] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> bool
    def delete_entry(self, entry_id: str) -> bool
    def search_entries(self, query: Optional[str] = None,
                      tags: Optional[List[str]] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      limit: int = 10) -> List[KnowledgeEntry]
    def save_to_disk(self, path: Optional[Union[str, Path]] = None) -> None
    def load_from_disk(self, path: Union[str, Path]) -> None
    def clear(self) -> None
```

### SEALKnowledge

```python
class SEALKnowledge:
    def __init__(self, knowledge_base: Optional[KnowledgeBase] = None)
    def enhance_prompt(self, prompt: str, max_examples: int = 3,
                      similarity_threshold: float = 0.3) -> str
    def learn_from_interaction(self, prompt: str, response: str,
                             metadata: Optional[Dict[str, Any]] = None,
                             tags: Optional[List[str]] = None) -> str
    def get_knowledge_for_task(self, task_description: str,
                             max_entries: int = 5) -> List[Dict[str, Any]]
    def clear_knowledge(self) -> None
```

## Best Practices

1. **Tagging**: Use consistent and meaningful tags for better retrieval
2. **Metadata**: Store additional context in the metadata field
3. **Versioning**: The system automatically tracks versions when entries are updated
4. **Persistence**: Save frequently to avoid data loss
5. **Search**: Use specific queries and tags for better search results

## Testing

Run the test suite with:

```bash
pytest tests/integration/seal/test_knowledge_base.py -v
```
