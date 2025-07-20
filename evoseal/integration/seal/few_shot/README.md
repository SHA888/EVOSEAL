# Few-Shot Learning for EVOSEAL

This module provides a flexible interface for few-shot learning capabilities in the EVOSEAL project. It's designed to work with various language models and adapters without requiring modifications to the base SEAL (Self-Adapting Language Models) submodule.

## Features

- **Flexible Example Management**: Store, retrieve, and manage few-shot examples
- **Dynamic Prompt Construction**: Build prompts with relevant examples based on input queries
- **Model Integration**: Works with any Hugging Face causal language model
- **Parameter-Efficient Fine-Tuning**: Uses LoRA (Low-Rank Adaptation) for efficient adaptation
- **Extensible Design**: Easy to extend with custom similarity metrics and prompt formats

## Installation

```bash
# Install required dependencies
pip install torch transformers peft datasets
```

## Usage

### Basic Usage

```python
from evoseal.integration.seal.few_shot import FewShotLearner, FewShotExample

# Initialize the learner
learner = FewShotLearner(
    base_model_name="meta-llama/Llama-3.2-1B-Instruct",
    lora_rank=16,
    lora_alpha=32,
    lora_dropout=0.05
)

# Add examples
learner.add_example(FewShotExample(
    input_data="What is the capital of France?",
    output_data="The capital of France is Paris.",
    metadata={"difficulty": "easy"}
))

# Generate a response
response = learner.generate("What is the capital of Italy?")
print(response)
```

### Fine-Tuning

```python
# Fine-tune the model on your examples
learner.fine_tune(
    output_dir="./few_shot_model",
    num_epochs=3,
    per_device_train_batch_size=4,
    learning_rate=2e-5
)

# Save and load examples
learner.save_examples("few_shot_examples.json")
loaded_examples = FewShotLearner.load_examples("few_shot_examples.json")
```

## API Reference

### `FewShotExample`

A dataclass representing a single few-shot example.

```python
FewShotExample(
    input_data: Any,          # Input data (text, structured data, etc.)
    output_data: Any,         # Expected output data
    metadata: Dict[str, Any]  # Optional metadata
)
```

### `FewShotLearner`

Main class for few-shot learning.

#### Initialization

```python
FewShotLearner(
    base_model_name: str = "meta-llama/Llama-3.2-1B-Instruct",
    lora_rank: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    device: Optional[str] = None,
    cache_dir: Optional[Union[str, Path]] = None
)
```

#### Key Methods

- `add_example(example: FewShotExample)`: Add a new few-shot example
- `remove_example(index: int)`: Remove an example by index
- `clear_examples()`: Remove all examples
- `get_relevant_examples(query: str, k: int = 5, **kwargs)`: Get k most relevant examples
- `format_prompt(query: str, examples: Optional[List[FewShotExample]] = None, **kwargs)`: Format a prompt with examples
- `generate(query: str, **generation_kwargs)`: Generate a response
- `fine_tune(output_dir: Union[str, Path], **training_kwargs)`: Fine-tune the model
- `save_examples(filepath: Union[str, Path])`: Save examples to a file
- `load_examples(filepath: Union[str, Path]) -> List[FewShotExample]`: Load examples from a file
- `load_pretrained(model_path: Union[str, Path])`: Load a fine-tuned model

## Advanced Usage

### Custom Prompt Formatting

```python
def custom_formatter(query: str, examples: List[FewShotExample]) -> str:
    """Custom prompt formatter."""
    prompt = "Answer the following question based on the examples:\n\n"

    for i, ex in enumerate(examples, 1):
        prompt += f"Example {i}:\n"
        prompt += f"Q: {ex.input_data}\n"
        prompt += f"A: {ex.output_data}\n\n"

    prompt += f"Q: {query}\nA:"
    return prompt

# Use custom formatter
response = learner.generate(
    "What is the capital of Spain?",
    format_func=custom_formatter
)
```

### Custom Similarity Metrics

```python
def custom_similarity(query: str, example: FewShotExample) -> float:
    """Custom similarity function."""
    # Implement your similarity logic here
    return 0.5  # Dummy value

# Use custom similarity function
learner.get_relevant_examples("query", similarity_func=custom_similarity)
```

## Testing

Run the test suite with pytest:

```bash
pytest tests/integration/seal/test_few_shot_learner.py -v
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
