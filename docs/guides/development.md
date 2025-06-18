# Development Guide

This guide provides information for developers who want to contribute to the EVOSEAL project.

## Prerequisites

- Python 3.10+
- Git
- [Poetry](https://python-poetry.org/) for dependency management
- [Pre-commit](https://pre-commit.com/) for code quality checks

## Getting Started

1. **Fork and Clone** the repository:
   ```bash
   git clone https://github.com/your-username/EVOSEAL.git
   cd EVOSEAL
   ```

2. **Set up the development environment**:
   ```bash
   # Install dependencies
   poetry install

   # Install pre-commit hooks
   pre-commit install
   ```

3. **Create a new branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Code Style

We use the following tools to maintain code quality:

- **Black** for code formatting
- **isort** for import sorting
- **Flake8** for linting
- **Mypy** for type checking

These are automatically run on commit via pre-commit hooks.

## Testing

Run the test suite with:

```bash
pytest
```

## Documentation

We use MkDocs with the Material theme for documentation. To serve the docs locally:

```bash
mkdocs serve
```

## Pull Requests

1. Ensure all tests pass
2. Update documentation as needed
3. Add/update unit tests
4. Run pre-commit checks
5. Open a PR with a clear description of changes

## Code Review Process

1. PRs require at least one approval
2. All CI checks must pass
3. Code must be well-documented
4. Follows project coding standards

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create a release tag
4. Push the tag to trigger deployment
