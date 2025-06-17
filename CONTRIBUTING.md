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
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements/dev.txt
   pre-commit install
   ```

## Development Workflow

1. Create a new branch for your feature or bugfix
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b bugfix/issue-number-short-description
   ```

2. Make your changes following the code style guidelines

3. Run tests and ensure they pass
   ```bash
   pytest
   ```

4. Commit your changes with a descriptive message
   ```bash
   git commit -m "feat: add new feature"
   # or
   git commit -m "fix: resolve issue with xyz"
   ```

5. Push your branch to your fork
   ```bash
   git push origin your-branch-name
   ```

6. Open a Pull Request against the `main` branch

## Code Style

We use the following tools to maintain code quality:

- **Black** for code formatting
- **isort** for import sorting
- **Flake8** for linting
- **Mypy** for type checking

These are automatically run on commit via pre-commit hooks.

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
