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

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/SHA888/EVOSEAL.git
   cd EVOSEAL
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
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

```
evoseal/
  core/           # Core functionality
  models/         # Model implementations
  evolvers/       # Evolution algorithms
  utils/          # Utility functions
  tests/          # Test files
  examples/       # Example scripts
  docs/           # Documentation
  scripts/        # Development scripts
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

   # Run linting
   flake8 evoseal

   # Run type checking
   mypy evoseal
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

- Place test files in the `tests/` directory
- Name test files with `test_` prefix
- Use descriptive test function names
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

### Building Documentation

```bash
# Install documentation dependencies
pip install -r docs/requirements.txt

# Build the documentation
mkdocs build

# Serve documentation locally
mkdocs serve
```

### Writing Documentation

- Update `docs/` directory
- Follow existing style
- Use Markdown
- Include examples
- Document public APIs

## Code Style

We use:
- **Black** for code formatting
- **isort** for import sorting
- **Flake8** for linting
- **Mypy** for type checking

These are enforced via pre-commit hooks.

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
