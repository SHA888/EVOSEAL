# Development Guide

Welcome to the EVOSEAL development guide! This document provides all the information you need to get started with development.

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Code Organization](#code-organization)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Documentation](#documentation)
- [Code Style](#code-style)
- [Dependency Management](#dependency-management)
- [Debugging](#debugging)
- [Performance Optimization](#performance-optimization)
- [Security Considerations](#security-considerations)
- [Release Process](#release-process)
- [Troubleshooting](#troubleshooting)

## Development Environment Setup

### Prerequisites

- Python 3.10+
- Git
- (Optional) Docker and Docker Compose
- (Optional) Task Master CLI for task management

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/SHA888/EVOSEAL.git
   cd EVOSEAL
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source .venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -r requirements/dev.txt
   pre-commit install
   ```

4. **Set up pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Run tests**
   ```bash
   pytest
   ```

## Code Organization

The project follows a modular architecture:

```
EVOSEAL/
├── evoseal/             # Main package
│   ├── core/            # Core framework components
│   │   ├── controller.py
│   │   ├── evaluator.py
│   │   ├── selection.py
│   │   └── version_database.py
│   │
│   ├── integration/     # Integration modules
│   │   ├── dgm/         # Darwin Godel Machine
│   │   ├── openevolve/  # OpenEvolve framework
│   │   └── seal/        # SEAL interface
│   │
│   ├── models/         # Data models and schemas
│   ├── providers/       # AI/ML model providers
│   ├── storage/         # Data persistence
│   ├── utils/           # Utility functions
│   └── examples/        # Example scripts and templates
│       ├── basic/       # Basic usage examples
│       ├── workflows/   # Workflow examples
│       └── templates/   # Project templates
│
├── config/            # Configuration files
├── docs/               # Documentation
├── scripts/            # Utility scripts
└── tests/              # Test suite
    ├── integration/    # Integration tests
    └── unit/           # Unit tests
```

## Development Workflow

1. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the code style guidelines
   - Write tests for new features
   - Update documentation

3. **Run tests and checks**
   ```bash
   # Run all tests
   pytest

   # Run tests with coverage
   pytest --cov=evoseal --cov-report=term-missing

   # Run specific test category
   pytest tests/unit/           # Unit tests
   pytest tests/integration/    # Integration tests

   # Run specific test file
   pytest tests/unit/core/test_controller.py

   # Run specific test function
   pytest tests/unit/core/test_controller.py::test_controller_initialization

   # Run with verbose output
   pytest -v

   # Run with debug output
   pytest --log-cli-level=DEBUG
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

5. **Push your changes**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a pull request**
   - Fill in the PR template
   - Request reviews
   - Address feedback

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_module.py

# Run tests with coverage
pytest --cov=evoseal tests/

# Generate HTML report
pytest --cov=evoseal --cov-report=html tests/
```

### Writing Tests

#### Test Organization

```
tests/
├── integration/          # Integration tests
│   ├── dgm/             # DGM integration tests
│   ├── openevolve/      # OpenEvolve integration tests
│   └── seal/            # SEAL integration tests
└── unit/                # Unit tests
    ├── core/            # Core components tests
    ├── models/          # Model tests
    ├── providers/       # Provider tests
    └── utils/           # Utility function tests
```

#### Best Practices

1. **Test Structure**:
   ```python
   def test_functionality():
       # Arrange
       # Set up test data and mocks
       
       # Act
       # Execute the code being tested
       
       # Assert
       # Verify the results
   ```

2. **Fixtures**:
   ```python
   import pytest
   
   @pytest.fixture
   def sample_config():
       return {"param": "value"}
   ```

3. **Mocks**:
   ```python
   from unittest.mock import Mock, patch
   
   def test_with_mock():
       mock_service = Mock()
       mock_service.method.return_value = "mocked"
       # Test with mock
   ```

4. **Parametrized Tests**:
   ```python
   import pytest
   
   @pytest.mark.parametrize("input,expected", [
       (1, 2),
       (2, 4),
       (3, 6),
   ])
   def test_multiply_by_two(input, expected):
       assert input * 2 == expected
   ```

- Follow the Arrange-Act-Assert pattern
- Use fixtures for common setup/teardown

Example:

```python
def test_feature():
    # Arrange
    input_value = 42
    expected = 42

    # Act
    result = some_function(input_value)

    # Assert
    assert result == expected
```

## Documentation

### Code Documentation

We use Google-style docstrings with type hints:

```python
def function_name(param1: type, param2: type) -> return_type:
    """Short description of the function.

    Longer description with more details about the function's behavior,
    parameters, return values, and any exceptions raised.

    Args:
        param1: Description of the first parameter.
        param2: Description of the second parameter.

    Returns:
        Description of the return value.

        Include the type in the description if not obvious.

        Can span multiple lines.

    Raises:
        ValueError: If the parameters are invalid.

    Examples:
        >>> result = function_name(1, 2)
        >>> print(result)
        3
    """
    pass
```

### Project Documentation

- `README.md`: Project overview and quick start
- `CHANGELOG.md`: Release notes and changes
- `docs/`: Detailed documentation
  - `user/`: User guides and tutorials
  - `api/`: API reference
  - `examples/`: Example usage
  - `development/`: Developer guides

### Building Documentation

```bash
# Install documentation dependencies
pip install -r docs/requirements.txt

# Build the docs
mkdocs build

# Serve the docs locally
mkdocs serve
```

- Follow existing style
- Use Markdown
- Include examples
- Document public APIs

## Code Style

### Automated Formatting

We use several tools to maintain consistent code style:

- **Black** - Code formatting
- **isort** - Import sorting
- **Ruff** - Linting and style enforcement
- **Mypy** - Static type checking
- **Blacken-docs** - Format code in documentation

### Pre-commit Hooks

Pre-commit hooks automatically run these checks before each commit:

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Type Hints

Use type hints for all function signatures and important variables:

```python
def process_data(data: list[dict[str, Any]]) -> pd.DataFrame:
    """Process input data into a DataFrame."""
    return pd.DataFrame(data)
```

### Naming Conventions

- **Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Classes**: `PascalCase`
- **Private**: `_private_var` (single underscore)
- **Dunder**: `__dunder__` (double underscore)

### Imports

Group imports in the following order:

1. Standard library imports
2. Third-party imports
3. Local application imports

With a blank line between each group:

```python
import os
from typing import Any, Optional

import numpy as np
import pandas as pd

from evoseal.core.controller import Controller
from evoseal.utils.helpers import helper_function
```

## Dependency Management

### Adding Dependencies

1. Add to appropriate requirements file:
   - `requirements/base.txt` for core dependencies
   - `requirements/dev.txt` for development tools
   - `requirements/requirements.txt` for pinned versions

2. Update `setup.py` if needed
3. Document in `CHANGELOG.md`

### Updating Dependencies

```bash
# Update a package
pip install -U package_name

# Update requirements files
pip freeze > requirements/requirements.txt
```

## Debugging

### Debugging Tests

```bash
# Drop into debugger on failure
pytest --pdb

# Print detailed output
pytest -v

# Run with logging
pytest --log-cli-level=DEBUG
```

### Debugging Production

- Check logs
- Enable debug mode
- Use remote debugging
- Profile performance

## Performance Optimization

### Profiling

```bash
# Install profiling tools
pip install pyinstrument

# Profile a script
python -m pyinstrument script.py
```

### Optimization Tips

- Use built-in functions
- Avoid unnecessary computations
- Use appropriate data structures
- Cache expensive operations
- Use async/await for I/O-bound operations

## Security Considerations

- Never commit secrets
- Validate all inputs
- Use parameterized queries
- Keep dependencies updated
- Follow the principle of least privilege

## Release Process

1. Update version in `__version__.py`
2. Update `CHANGELOG.md`
3. Create a release branch
4. Run all tests
5. Build and test the package
6. Create a GitHub release
7. Publish to PyPI

## Troubleshooting

### Common Issues

1. **Tests failing**
   - Check for syntax errors
   - Verify test data
   - Check for environment issues

2. **Dependency conflicts**
   - Recreate virtual environment
   - Check for version conflicts
   - Update requirements

3. **Documentation not building**
   - Check for markdown errors
   - Verify dependencies
   - Check build logs

## Getting Help

- Check the [documentation](https://sha888.github.io/EVOSEAL/)
- Search [issues](https://github.com/SHA888/EVOSEAL/issues)
- Open a new issue if needed
