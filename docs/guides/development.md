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
   # Create and activate virtual environment
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate

   # Install development dependencies
   pip install -r requirements-dev.txt

   # Install package in development mode
   pip install -e .

   # Install pre-commit hooks
   pre-commit install
   ```

3. **Create a new branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Code Style and Quality

We maintain high code quality using several tools:

### Pre-commit Hooks
Automatically run on each commit:
- **Black** - Code formatting
- **isort** - Import sorting
- **Ruff** - Linting and style enforcement
- **Mypy** - Static type checking
- **Blacken-docs** - Format code in documentation

### Manual Checks
Run these before pushing:
```bash
# Format code with Black
black .


# Sort imports
isort .


# Run type checking
mypy .


# Run linter
ruff check .
```

### Pre-commit Installation
```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install
```

## Project Structure

```
evoseal/
├── core/               # Core framework components
├── integration/        # Integration modules (DGM, OpenEvolve, SEAL)
├── models/            # Data models
├── providers/         # AI/ML model providers
├── storage/           # Data persistence
├── utils/             # Utility functions
└── examples/          # Example scripts and templates
```

## Testing

Run the test suite with:

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run tests with coverage
pytest --cov=evoseal tests/
```
```

## Documentation

We use MkDocs with the Material theme for documentation. To serve the docs locally:

```bash
mkdocs serve
```

## Development Workflow

### Using Task Master
We use `task-master` for task management:

```bash
# List all tasks
task-master list

# Show details of a task
task-master show <task_id>

# Mark a task as done
task-master set-status --id=<task_id> --status=done

# Generate task files
task-master generate
```

### Pull Request Process
1. Ensure all tests pass
2. Update documentation as needed
3. Run pre-commit checks
4. Create a pull request with:
   - Clear description of changes
   - Related issue numbers
   - Screenshots if applicable
   - Updated documentation

### Versioning
- We follow [Semantic Versioning](https://semver.org/)
- Update version in `evoseal/__version__.py`
- Update `CHANGELOG.md` with release notes

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
