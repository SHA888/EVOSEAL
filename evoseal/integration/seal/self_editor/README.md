# SelfEditor Module

The SelfEditor module enables the SEAL system to review and improve its own outputs through configurable editing strategies and criteria.

## Features

- **Configurable Editing Criteria**: Define what constitutes high-quality content
- **Multiple Edit Operations**: Support for various edit types (add, remove, replace, rewrite, etc.)
- **Edit History**: Track all changes made to content over time
- **Flexible Strategies**: Customizable editing strategies via the `EditStrategy` protocol
- **Confidence-based Application**: Apply suggestions based on confidence thresholds

## Usage

### Basic Usage

```python
from evoseal.integration.seal.self_editor import SelfEditor

# Create a SelfEditor instance
editor = SelfEditor(auto_apply=True)

# Evaluate some content
content = "The system is design to learning from few examples."
suggestions = editor.evaluate_content(content, content_id="example_1")

# Review suggestions
for suggestion in suggestions:
    print(f"Suggestion: {suggestion.operation}")
    print(f"Original: {suggestion.original_text}")
    print(f"Suggested: {suggestion.suggested_text}")
    print(f"Confidence: {suggestion.confidence:.2f}")
    print(f"Reason: {suggestion.explanation}")
    print("-" * 50)
```

### Custom Editing Strategy

```python
from evoseal.integration.seal.self_editor import (
    SelfEditor, 
    EditStrategy, 
    EditSuggestion,
    EditOperation,
    EditCriteria
)

class GrammarCheckStrategy(EditStrategy):
    """A simple grammar checking strategy."""
    
    def evaluate(self, content: str, **kwargs) -> list[EditSuggestion]:
        # In a real implementation, this would use a grammar checking library
        suggestions = []
        
        # Example: Check for common errors
        if "design to" in content and "designed to" not in content:
            suggestions.append(EditSuggestion(
                operation=EditOperation.REPLACE,
                criteria=[EditCriteria.GRAMMAR],
                original_text="design to",
                suggested_text="designed to",
                confidence=0.9,
                explanation="Correct verb form should be 'designed to' in this context"
            ))
            
        return suggestions
    
    def apply_edit(self, content: str, suggestion: EditSuggestion) -> str:
        return content.replace(suggestion.original_text, suggestion.suggested_text)

# Use the custom strategy
editor = SelfEditor(strategy=GrammarCheckStrategy())
```

### Tracking Edit History

```python
# Create an editor with history tracking
editor = SelfEditor()

# Evaluate and track changes
content = "Initial content with some issues."
content_id = "doc_123"

# First evaluation
suggestions = editor.evaluate_content(content, content_id=content_id)
for suggestion in suggestions:
    if suggestion.confidence > 0.8:  # Apply high-confidence suggestions
        editor.apply_edit(content_id, suggestion, apply=True)

# Get the current version
current = editor.get_current_content(content_id)
print(f"Current content: {current}")

# View edit history
history = editor.get_edit_history(content_id)
for edit in history.edit_history:
    print(f"{edit['timestamp']} - {edit['suggestion']['operation']} - {edit['applied']}")
```

## API Reference

### `SelfEditor` Class

#### `__init__(self, strategy=None, auto_apply=False, min_confidence=0.7, history_limit=100)`

Initialize the SelfEditor.

- `strategy`: An implementation of `EditStrategy` to use for evaluating content
- `auto_apply`: If True, suggestions with confidence >= min_confidence will be automatically applied
- `min_confidence`: Minimum confidence threshold (0.0-1.0) for auto-applying suggestions
- `history_limit`: Maximum number of edit histories to keep in memory

#### `evaluate_content(self, content, content_id=None, **kwargs)`

Evaluate content and return suggested edits.

- `content`: The content to evaluate
- `content_id`: Optional identifier for tracking edit history
- `**kwargs`: Additional arguments to pass to the evaluation strategy
- Returns: List of `EditSuggestion` objects

#### `apply_edit(self, content_id, suggestion, apply=True)`

Apply or reject an edit suggestion.

- `content_id`: ID of the content to edit
- `suggestion`: The `EditSuggestion` to apply
- `apply`: If True, apply the edit; if False, just record it
- Returns: The edited content if applied, or the original content if not
- Raises: `KeyError` if no content exists with the given ID

#### `get_edit_history(self, content_id)`

Get the edit history for a piece of content.

- `content_id`: The ID of the content
- Returns: `EditHistory` object or None if not found

#### `get_current_content(self, content_id)`

Get the current version of a piece of content.

- `content_id`: The ID of the content
- Returns: The current content string or None if not found

#### `reset_content(self, content_id)`

Reset content to its original state.

- `content_id`: The ID of the content to reset
- Returns: The original content or None if not found

## Extending Functionality

To create a custom editing strategy, implement the `EditStrategy` protocol:

```python
class MyCustomStrategy(EditStrategy):
    def evaluate(self, content: str, **kwargs) -> list[EditSuggestion]:
        # Your evaluation logic here
        pass
    
    def apply_edit(self, content: str, suggestion: EditSuggestion) -> str:
        # Your edit application logic here
        pass
```

## Testing

Run the test suite with:

```bash
pytest tests/integration/seal/test_self_editor.py
```
