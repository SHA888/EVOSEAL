# Contributing to EVOSEAL

Thank you for your interest in contributing to EVOSEAL! We appreciate your time and effort in helping us improve this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)
- [License](#license)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
   ```bash
   git clone https://github.com/your-username/EVOSEAL.git
   cd EVOSEAL
   ```
3. **Set up** the development environment
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
   ```bash
   python -m venv venv
   source .venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements/dev.txt
   pre-commit install
   ```

---

### Configuration for Contributors

- EVOSEAL uses YAML files for most configuration. See `configs/evoseal.yaml` and the [CONFIGURATION.md](CONFIGURATION.md) guide.
- Use the `SystemConfig` model (`evoseal.models.system_config.SystemConfig`) to load and validate configuration in new code:
  ```python
  from evoseal.models.system_config import SystemConfig
  config = SystemConfig.from_yaml('configs/evoseal.yaml')
  config.validate()
  value = config.get('dgm.max_iterations')
  ```
- Ensure any new configuration keys are documented and, if required, validated in your code.

## Development Workflow

### Task Management

We use `task-master` to manage development tasks. Before starting work:

1. Check available tasks:
   ```bash
   task-master list
   ```

2. Select a task to work on and mark it as in progress:
   ```bash
   task-master set-status --id=<task_id> --status=in-progress
   ```

### Making Changes

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-number-description
   ```

2. Make your changes following the code style guidelines

3. Run tests to ensure everything works:
   ```bash
   # Run all tests
   pytest
   
   # Run tests with coverage
   pytest --cov=evoseal
   
   # Run specific test file
   pytest tests/unit/test_module.py
   ```

4. Update documentation if needed

5. Run pre-commit checks:
   ```bash
   pre-commit run --all-files
   ```

6. Commit your changes with a descriptive message:
   ```bash
   git commit -m "feat: add new feature for X"
   ```
   
   Follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.

7. Push your branch to GitHub:
   ```bash
   git push origin your-branch-name
   ```

8. Open a Pull Request against the `main` branch

9. After PR is merged, mark the task as done:
   ```bash
   task-master set-status --id=<task_id> --status=done
   ```

## Code Style

We enforce code style using several tools:

### Formatting
- **Black** for code formatting
- **isort** for import sorting
- **Ruff** for linting
- **Mypy** for type checking

### Guidelines
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Use type hints for all function signatures
- Keep lines under 88 characters
- Use double quotes for strings
- Use absolute imports
- Document all public APIs with docstrings

### Pre-commit Hooks
We use pre-commit to automatically run these checks before each commit. To set up:

```bash
pip install pre-commit
pre-commit install
```

To run checks manually:
```bash
pre-commit run --all-files
```

## Testing

- Write tests for new features and bug fixes
- Ensure all tests pass before submitting a PR
- Follow the existing test patterns
- Use descriptive test names
- Test edge cases and error conditions

## Documentation

- Update documentation when adding new features or changing behavior
- Follow the existing documentation style
- Add docstrings to all public functions and classes
- Include examples where helpful

## Pull Request Process

1. Ensure your code follows the style guidelines
2. Update the documentation as needed
3. Add tests for new features
4. Ensure all tests pass
5. Update the CHANGELOG.md with your changes
6. Request review from at least one maintainer
7. Address any feedback

## Reporting Issues

When reporting issues, please include:

- A clear title and description
- Steps to reproduce the issue
- Expected vs. actual behavior
- Environment details (OS, Python version, etc.)
- Any relevant logs or error messages

## Feature Requests

We welcome feature requests! Please:

1. Check if the feature already exists
2. Explain why this feature would be valuable
3. Include any relevant use cases
4. Consider opening a discussion first for significant changes

## License

By contributing, you agree that your contributions will be licensed under the project's [LICENSE](LICENSE) file.
