# Development Guide

Welcome to the EVOSEAL development guide! This comprehensive document provides all the information you need to get started with development and contribute effectively to the project.

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
- (Recommended) [Pre-commit](https://pre-commit.com/) for code quality checks

### Quick Start

1. **Fork and Clone** the repository:
   ```bash
   git clone https://github.com/your-username/EVOSEAL.git
   cd EVOSEAL
   ```

2. **Set up a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies**:
   ```bash
   pip install -r requirements/dev.txt
   pip install -e .  # Install package in development mode
   ```

4. **Set up pre-commit hooks**:
   ```bash
   pre-commit install
   ```

5. **Verify installation**:
   ```bash
   python -m pytest tests/
   python -c "import evoseal; print('Installation successful!')"
   ```

6. **Create a new branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

### Alternative Setup with Docker

```bash
# Build development container
docker-compose -f docker-compose.dev.yml build

# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Access the container
docker-compose -f docker-compose.dev.yml exec evoseal bash
```

## Code Organization

### Project Structure

```
evoseal/
├── core/                    # Core framework components
├── integration/            # Integration modules (DGM, OpenEvolve, SEAL (Self-Adapting Language Models))
├── agents/                # Agent implementations
├── providers/             # AI/ML model providers
├── models/                # Data models and schemas
├── storage/               # Data persistence
└── utils/                 # Utility functions

tests/
├── unit/                  # Unit tests
├── integration/           # Integration tests
├── regression/            # Regression tests
└── safety/                # Safety and security tests

docs/
├── api/                   # API documentation
├── guides/                # User and developer guides
├── architecture/          # Architecture documentation
├── safety/                # Safety documentation
└── core/                  # Core system documentation
```

### Coding Conventions

- **Modules**: Use snake_case for module names
- **Classes**: Use PascalCase for class names
- **Functions**: Use snake_case for function names
- **Constants**: Use UPPER_CASE for constants
- **Private members**: Prefix with single underscore `_`
- **Type hints**: Always include type hints for public APIs

## Development Workflow

### 1. Planning
- Check existing issues and discussions
- Create or update issue for your feature/fix
- Discuss approach with maintainers if needed

### 2. Development
- Create feature branch from `main`
- Write code following style guidelines
- Add comprehensive tests
- Update documentation

### 3. Testing
- Run unit tests: `pytest tests/unit/`
- Run integration tests: `pytest tests/integration/`
- Run safety tests: `pytest tests/safety/`
- Check code coverage: `pytest --cov=evoseal`

### 4. Quality Checks
- Format code: `black evoseal tests`
- Sort imports: `isort evoseal tests`
- Lint code: `ruff check evoseal tests`
- Type check: `mypy evoseal`
- Security scan: `bandit -r evoseal`

### 5. Documentation
- Update docstrings for new/modified functions
- Update relevant documentation files
- Add examples if introducing new features

### 6. Submission
- Commit changes with descriptive messages
- Push branch to your fork
- Create pull request with detailed description
- Address review feedback

## Testing

### Test Categories

#### Unit Tests
- Test individual functions and classes
- Mock external dependencies
- Fast execution (< 1s per test)
- Location: `tests/unit/`

#### Integration Tests
- Test component interactions
- Use real dependencies where possible
- Moderate execution time
- Location: `tests/integration/`

#### Safety Tests
- Test safety mechanisms and rollback
- Critical for production readiness
- Location: `tests/safety/`

#### Regression Tests
- Test for performance regressions
- Benchmark critical paths
- Location: `tests/regression/`

### Running Tests

```bash
# Run all tests
pytest

# Run specific test category
pytest tests/unit/
pytest tests/integration/
pytest tests/safety/

# Run with coverage
pytest --cov=evoseal --cov-report=html

# Run specific test file
pytest tests/unit/test_evolution_pipeline.py

# Run with verbose output
pytest -v

# Run tests matching pattern
pytest -k "test_safety"
```

### Writing Tests

```python
import pytest
from unittest.mock import Mock, patch
from evoseal.core import EvolutionPipeline

class TestEvolutionPipeline:
    def test_initialization(self):
        """Test pipeline initialization."""
        pipeline = EvolutionPipeline()
        assert pipeline is not None

    @patch('evoseal.core.evolution_pipeline.SomeExternalService')
    def test_with_mock(self, mock_service):
        """Test with mocked external dependency."""
        mock_service.return_value.process.return_value = "success"
        pipeline = EvolutionPipeline()
        result = pipeline.run()
        assert result == "success"

    def test_error_handling(self):
        """Test error handling."""
        pipeline = EvolutionPipeline()
        with pytest.raises(ValueError):
            pipeline.run(invalid_param=True)
```

## Code Style and Quality

### Pre-commit Hooks
Automatically run on each commit:
- **Black** - Code formatting
- **isort** - Import sorting
- **Ruff** - Linting and style enforcement
- **Mypy** - Static type checking
- **Bandit** - Security scanning
- **Safety** - Dependency vulnerability scanning

### Manual Quality Checks

```bash
# Format code
black evoseal tests

# Sort imports
isort evoseal tests

# Lint code
ruff check evoseal tests

# Type checking
mypy evoseal

# Security scanning
bandit -r evoseal

# Dependency vulnerability check
safety check
```

### Code Style Guidelines

- **Line length**: 88 characters (Black default)
- **Docstrings**: Google style docstrings
- **Type hints**: Required for all public APIs
- **Error handling**: Use specific exception types
- **Logging**: Use structured logging with appropriate levels

## Dependency Management

### Requirements Files

- `requirements.txt` - Base runtime dependencies
- `requirements/dev.txt` - Development dependencies
- `requirements/test.txt` - Testing dependencies
- `requirements/docs.txt` - Documentation dependencies

### Adding Dependencies

1. Add to appropriate requirements file
2. Pin versions for stability
3. Update `requirements/requirements.txt` with `pip freeze`
4. Test with new dependencies
5. Update documentation if needed

### Dependency Updates

```bash
# Check for outdated packages
pip list --outdated

# Update specific package
pip install --upgrade package_name

# Regenerate frozen requirements
pip freeze > requirements/requirements.txt
```

## Debugging

### Debug Configuration

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Use debugger
import pdb; pdb.set_trace()

# Or use ipdb for better experience
import ipdb; ipdb.set_trace()
```

### Common Debugging Scenarios

#### Evolution Pipeline Issues
- Check component initialization
- Verify configuration files
- Review event system logs
- Validate safety mechanisms

#### Integration Problems
- Test components individually
- Check API credentials
- Verify network connectivity
- Review error logs

#### Performance Issues
- Profile with cProfile
- Monitor memory usage
- Check database queries
- Review algorithm complexity

## Performance Optimization

### Profiling

```bash
# Profile with cProfile
python -m cProfile -o profile.stats your_script.py

# Analyze profile
python -c "import pstats; p=pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"

# Memory profiling
pip install memory-profiler
python -m memory_profiler your_script.py
```

### Optimization Guidelines

- **Algorithms**: Choose appropriate data structures
- **Database**: Optimize queries and use indexes
- **Caching**: Cache expensive computations
- **Async**: Use async/await for I/O operations
- **Parallelism**: Use multiprocessing for CPU-bound tasks

## Security Considerations

### Code Security
- Never commit API keys or secrets
- Use environment variables for sensitive data
- Validate all inputs
- Sanitize user-provided data
- Use secure random number generation

### Dependency Security
- Regularly update dependencies
- Use `safety` to check for vulnerabilities
- Review dependency licenses
- Minimize dependency count

### Runtime Security
- Run with minimal privileges
- Use sandboxed execution for untrusted code
- Implement proper error handling
- Log security-relevant events

## Release Process

### Version Numbering
- Follow [Semantic Versioning](https://semver.org/)
- Format: `MAJOR.MINOR.PATCH`
- Pre-release: `MAJOR.MINOR.PATCH-alpha.N`

### Release Checklist

1. **Pre-release**:
   - [ ] All tests passing
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated
   - [ ] Version bumped

2. **Release**:
   - [ ] Create release branch
   - [ ] Final testing
   - [ ] Create GitHub release
   - [ ] Deploy to PyPI
   - [ ] Update documentation

3. **Post-release**:
   - [ ] Merge to main
   - [ ] Create next development branch
   - [ ] Announce release

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure package is installed in development mode
pip install -e .

# Check Python path
python -c "import sys; print(sys.path)"
```

#### Test Failures
```bash
# Run tests with verbose output
pytest -v --tb=long

# Run specific failing test
pytest tests/path/to/test.py::test_function -v
```

#### Pre-commit Hook Failures
```bash
# Run hooks manually
pre-commit run --all-files

# Skip hooks temporarily (not recommended)
git commit --no-verify
```

#### Performance Issues
```bash
# Profile the application
python -m cProfile -o profile.stats main.py

# Check memory usage
python -m memory_profiler main.py
```

### Getting Help

1. **Documentation**: Check docs/ directory
2. **Issues**: Search existing GitHub issues
3. **Discussions**: Use GitHub Discussions
4. **Community**: Join our Discord/Slack
5. **Maintainers**: Contact project maintainers

## Contributing Guidelines

### Code of Conduct
- Be respectful and inclusive
- Follow our Code of Conduct
- Help create a welcoming environment

### Contribution Process
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests and documentation
5. Submit a pull request
6. Respond to review feedback

### Pull Request Guidelines
- Clear, descriptive title
- Detailed description of changes
- Link to related issues
- Include tests for new functionality
- Update documentation as needed
- Ensure all checks pass

Thank you for contributing to EVOSEAL! Your efforts help make this project better for everyone.
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
├── integration/        # Integration modules (DGM, OpenEvolve, SEAL (Self-Adapting Language Models))
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
