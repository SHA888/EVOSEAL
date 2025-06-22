# Testing Guide

This document provides guidelines and instructions for testing the EVOSEAL project.

## Table of Contents

- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Test Organization](#test-organization)
- [Test Coverage](#test-coverage)
- [Continuous Integration](#continuous-integration)
- [Debugging Tests](#debugging-tests)
- [Best Practices](#best-practices)

## Running Tests

### Prerequisites

Make sure you have installed the development dependencies:

```bash
pip install -r requirements-dev.txt
pip install -e .  # Install package in development mode
```

### Running Tests

#### Run All Tests

```bash
pytest
```

#### Run Tests by Category

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Test a specific file
pytest tests/unit/test_module.py

# Test a specific function
pytest tests/unit/test_module.py::test_function_name
```

#### Run with Coverage

```bash
pytest --cov=evoseal --cov-report=term-missing
```

#### Run with Verbose Output

```bash
pytest -v
```

#### Run with Debug Output

```bash
pytest --log-cli-level=DEBUG
```

### Test Organization

Tests follow the same structure as the source code:

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

### Test Naming Conventions

- Test files should be named `test_*.py` or `*_test.py`
- Test functions should be named `test_*`
- Test classes should be named `Test*`
- Test methods should be named `test_*`

## Writing Tests

### Writing Good Tests

1. **Isolation**: Each test should be independent and not rely on the state from other tests
2. **Descriptive Names**: Test names should clearly describe what they're testing
3. **AAA Pattern**: Follow Arrange-Act-Assert pattern
4. **Test Coverage**: Aim for high test coverage, especially for critical paths
5. **Mocks**: Use mocks for external services and slow operations

### Example Test

```python
def test_controller_initialization():
    # Arrange
    mock_evaluator = Mock()
    mock_selector = Mock()

    # Act
    controller = Controller(evaluator=mock_evaluator, selector=mock_selector)

    # Assert
    assert controller.evaluator == mock_evaluator
    assert controller.selector == mock_selector
```

### Fixtures

Use fixtures for common test setup:

```python
import pytest

@pytest.fixture
def sample_config():
    return {
        'population_size': 100,
        'mutation_rate': 0.1,
        'crossover_rate': 0.8
    }

def test_evolution_config(sample_config):
    assert sample_config['population_size'] == 100
```

## Test Coverage

To generate a coverage report:

```bash
pytest --cov=evoseal tests/
```

For an HTML report:

```bash
pytest --cov=evoseal --cov-report=html tests/
open htmlcov/index.html  # On macOS
```

## Continuous Integration

Tests are automatically run on every push and pull request using GitHub Actions. The CI pipeline includes:

- Unit tests
- Integration tests
- Code coverage reporting
- Linting and type checking

## Debugging Tests

### PDB Debugger

Drop into the Python debugger on test failure:

```bash
pytest --pdb
```

### Verbose Output

Get more detailed test output:

```bash
pytest -v
```

### Test Logging

To see log output during tests:

```bash
pytest --log-cli-level=INFO
```

## Best Practices

1. **Isolation**: Tests should be isolated and not depend on each other
2. **Deterministic**: Tests should produce the same results every time they're run
3. **Fast**: Keep tests fast to encourage frequent testing
4. **Descriptive**: Use descriptive test function names and docstrings
5. **Edge Cases**: Test edge cases and error conditions
6. **Mocks**: Use mocks for external dependencies
7. **Fixtures**: Use fixtures for common test setup
8. **CI**: Ensure all tests pass before merging to main

- **Arrange-Act-Assert**: Structure tests with clear sections
- **One Assert Per Test**: Each test should verify one thing
- **Test Naming**: Use descriptive names like `test_function_name_when_condition_then_result`
- **Docstrings**: Include docstrings explaining what's being tested

## Performance Testing

For performance-critical code, consider adding benchmarks:

```python
def test_performance(benchmark):
    result = benchmark(some_function, arg1, arg2)
    assert result is not None
```

Run with:

```bash
pytest --benchmark-only
```

## Security Testing

- Test for common vulnerabilities (injection, XSS, etc.)
- Use tools like Bandit for security scanning
- Never include sensitive data in test code

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Python Testing with pytest](https://pythontest.com/pytest-book/)
