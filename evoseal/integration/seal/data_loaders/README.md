# Data Loaders Module

This module provides utilities for loading, parsing, and managing knowledge and examples from various sources and formats in the SEAL system.

## Features

- **Multiple Format Support**: Load data from JSON, YAML, and CSV files
- **Type Safety**: Built-in support for Pydantic model validation
- **Batch Processing**: Load multiple files in parallel
- **Caching**: Built-in caching to improve performance
- **Extensible**: Easy to add support for additional formats

## Installation

This module is part of the SEAL system. No additional installation is required.

## Usage

### Basic Usage

```python
from pathlib import Path
from pydantic import BaseModel
from evoseal.integration.seal.data_loaders import load_data

# Define your data model
class ExampleModel(BaseModel):
    id: str
    name: str
    value: int

# Load data from a file
data = load_data("examples/data.json", ExampleModel)

# Or with explicit format
data = load_data("examples/data.yaml", ExampleModel, format="yaml")
```

### Batch Processing

```python
from evoseal.integration.seal.data_loaders import load_batch

# Load multiple files in parallel
data = load_batch(
    ["data/file1.json", "data/file2.json"],
    ExampleModel,
    max_workers=4
)

# Or load all files in a directory
data = load_batch(
    "data/",
    ExampleModel,
    pattern="*.json",  # Only load JSON files
    recursive=True     # Search subdirectories
)
```

### Caching

```python
from evoseal.integration.seal.data_loaders import cached, default_cache

# Clear the cache
default_cache.clear()

# Use the cache decorator
@cached(ttl=3600)  # Cache for 1 hour
def load_expensive_data():
    return load_data("large_dataset.json", ExampleModel)
```

## API Reference

### Main Functions

- `load_data(source, model, format=None, **kwargs)`: Load data from a source with automatic format detection
- `load_batch(sources, model, max_workers=4, **kwargs)`: Load multiple files in parallel
- `get_loader(format)`: Get the appropriate loader for a given format

### Loaders

- `DataLoader`: Abstract base class for data loaders
- `JSONLoader`: Loader for JSON data
- `YAMLLoader`: Loader for YAML data
- `CSVLoader`: Loader for CSV data

### Caching

- `DataCache`: Cache implementation for data loaders
- `default_cache`: Default cache instance
- `cached`: Decorator for caching function results

## Adding a New Format

To add support for a new format:

1. Create a new loader class that inherits from `DataLoader`
2. Implement the `from_string` method
3. Update the `get_loader` function to include your new loader

## License

This module is part of the SEAL system and is licensed under the same terms.
