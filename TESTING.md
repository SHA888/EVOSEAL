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
pip install -r requirements/dev.txt
```

### Running All Tests

To run all tests:

```bash
pytest
```

### Running Specific Tests

Run tests in a specific file:

```bash
pytest tests/test_module.py
```

Run a specific test function:

```bash
pytest tests/test_module.py::test_function_name
```

### Test Coverage

To generate a coverage report:

```bash
pytest --cov=evoseal tests/
```

For an HTML report:

```bash
pytest --cov=evoseal --cov-report=html tests/
open htmlcov/index.html  # On macOS
```

## Writing Tests

### Test Structure

Tests are organized in the `tests/` directory, mirroring the structure of the `evoseal/` package. For example:

```
evoseal/
  module/
    __init__.py
    module.py
tests/
  module/
    __init__.py
    test_module.py
```

### Example Test

```python
import pytest
from evoseal.module import some_function

def test_some_function():
    """Test that some_function returns expected results."""
    # Setup
    input_value = "test"
    expected = "expected output"

    # Exercise
    result = some_function(input_value)

    # Verify
    assert result == expected

    # Cleanup (if needed)
```

### Fixtures

Use fixtures for common test setup and teardown:

```python
import pytest

@pytest.fixture
test_data():
    """Provide test data for tests."""
    data = {"key": "value"}
    yield data
    # Cleanup code here

def test_with_fixture(test_data):
    assert "key" in test_data
```

## Test Organization

### Unit Tests

- Test individual functions and classes in isolation
- Place in `tests/unit/`
- Should be fast and not require external services

### Integration Tests

- Test interactions between components
- Place in `tests/integration/`
- May require external services or databases

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

## Writing Good Tests

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
