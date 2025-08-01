# EVOSEAL CI/CD Workflow Documentation

This document provides a comprehensive guide to the EVOSEAL project's Continuous Integration and Continuous Deployment (CI/CD) workflow. The workflow is designed to ensure code quality, security, and reliable releases.

## Table of Contents
- [Overview](#overview)
- [Workflow Triggers](#workflow-triggers)
- [Workflow Structure](#workflow-structure)
- [Versioning and Releases](#versioning-and-releases)
- [Testing Strategy](#testing-strategy)
- [Security Scanning](#security-scanning)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

The EVOSEAL CI/CD pipeline is implemented using GitHub Actions and consists of several interconnected workflows that handle different aspects of the development and release process. The main workflows are:

1. **CI Pipeline** (`ci.yml`): Runs on every push and PR, handling validation, testing, and security scanning.
2. **Release Workflow** (`release.yml`): Manages the release process, including version bumping and package publishing.
3. **Security Scanning**: Integrated into the CI pipeline to ensure code quality and security.

## Workflow Triggers

### CI Pipeline
- **On push to any branch**: Runs validation, testing, and security checks
- **On pull request**: Runs validation and testing
- **Scheduled**: Weekly security scanning on the main branch

### Release Workflow
- **Manual trigger**: Via GitHub UI with version bump type (major/minor/patch)
- **On tag push**: For versioned releases (tags matching `v*.*.*`)
- **On successful CI completion**: For main and release/* branches

## Workflow Structure

### 1. CI Pipeline (`ci.yml`)

#### Validation
- Code formatting (Black, isort, Ruff)
- Type checking (mypy)
- Linting (Ruff)
- Documentation build verification

#### Testing
- **Unit Tests**: Run on all supported Python versions and operating systems
- **Integration Tests**: Run on Ubuntu with Python 3.10
- **Test Coverage**: Code coverage reporting via Codecov
- **Artifact Collection**: Test results and coverage reports stored as artifacts

#### Security Scanning
- **Static Analysis**: Bandit for Python code
- **Dependency Scanning**: Safety and pip-audit
- **Secret Detection**: detect-secrets
- **Advanced Analysis**: Semgrep for complex security patterns

### 2. Release Workflow (`release.yml`)

#### Version Management
- Automated version bumping (major/minor/patch)
- Changelog generation
- Git tagging

#### Package Publishing
- Builds source distribution and wheel
- Publishes to PyPI
- Creates GitHub release with release notes

## Versioning and Releases

### Version Bumping

Versions follow [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):

- **MAJOR**: Incompatible API changes
- **MINOR**: Backwards-compatible functionality
- **PATCH**: Backwards-compatible bug fixes

### Creating a Release

1. **Prepare the Release**:
   ```bash
   # Bump version (choose one)
   python scripts/bump_version.py major   # 1.0.0 -> 2.0.0
   python scripts/bump_version.py minor   # 1.0.0 -> 1.1.0
   python scripts/bump_version.py patch   # 1.0.0 -> 1.0.1
   python scripts/bump_version.py 2.0.0   # Set specific version
   ```

2. **Manual Release (GitHub UI)**:
   - Go to Actions → Release Workflow
   - Click "Run workflow"
   - Select version bump type or specific version
   - Click "Run workflow"

3. **Automated Release (Tag Push)**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

## Testing Strategy

### Test Types

1. **Unit Tests**:
   - Test individual components in isolation
   - Fast execution
   - High code coverage target (90%+)

2. **Integration Tests**:
   - Test component interactions
   - Include database and external service integrations
   - Run on Ubuntu with Python 3.10

### Test Execution

Run tests locally:
```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run with coverage
pytest --cov=evoseal --cov-report=term-missing
```

## Security Scanning

### Tools Used

- **Bandit**: Static analysis for common security issues
- **Safety**: Checks Python dependencies for known vulnerabilities
- **detect-secrets**: Prevents committing sensitive information
- **pip-audit**: Audits Python packages for known vulnerabilities
- **Semgrep**: Advanced static analysis for security issues

### Running Security Scans Locally

```bash
# Install security tools
pip install bandit safety detect-secrets pip-audit semgrep

# Run Bandit
bandit -r evoseal/

# Run Safety
safety check

# Run detect-secrets
detect-secrets scan --update .secrets.baseline

# Run pip-audit
pip-audit

# Run Semgrep
semgrep --config=auto .
```

## Troubleshooting

### Common Issues

1. **Failing Tests**
   - Check the test logs in the GitHub Actions output
   - Run tests locally with `pytest -v` for detailed output
   - Ensure all dependencies are installed

2. **Version Conflicts**
   - Ensure `pyproject.toml` has the correct version
   - Check for merge conflicts in version-related files

3. **Publishing Failures**
   - Verify PyPI token has correct permissions
   - Check if the version already exists on PyPI

## Best Practices

### For Developers
- Always run tests locally before pushing
- Write meaningful commit messages
- Keep PRs focused and small
- Update documentation when making changes

### For Maintainers
- Review security scan results before releases
- Monitor dependency updates for security vulnerabilities
- Keep CI/CD workflows up to date
- Document any workflow changes

### For Contributors
- Fork the repository and create feature branches
- Open a draft PR early for feedback
- Ensure all tests pass before marking PR as ready for review
- Update documentation as needed

---

*Last updated: August 2024*
