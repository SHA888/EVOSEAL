# EVOSEAL CI/CD Quick Start

This guide provides a quick reference for common CI/CD tasks in the EVOSEAL project.

## Prerequisites

- Python 3.9+
- Git
- GitHub account with access to the repository

## Common Tasks

### Running Tests Locally

```bash
# Install development dependencies
pip install -e ".[test]"

# Run all tests
pytest

# Run with coverage report
pytest --cov=evoseal --cov-report=term-missing
```

### Creating a New Release

1. Bump the version (choose one):
   ```bash
   # For a patch release (1.0.0 -> 1.0.1)
   python scripts/bump_version.py patch

   # For a minor release (1.0.0 -> 1.1.0)
   python scripts/bump_version.py minor

   # For a major release (1.0.0 -> 2.0.0)
   python scripts/bump_version.py major

   # For a specific version
   python scripts/bump_version.py 2.1.0
   ```

2. Push the changes and create a tag:
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "chore: release vX.Y.Z"
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```

3. The release workflow will automatically:
   - Build the package
   - Run all tests
   - Publish to PyPI
   - Create a GitHub release

### Running Security Scans

```bash
# Install security tools
pip install bandit safety detect-secrets pip-audit semgrep

# Run all security scans
make security-scan
```

## GitHub Actions

### Manual Workflow Triggers

1. **Run CI Pipeline**:
   - Go to Actions → CI Pipeline
   - Click "Run workflow"
   - Select branch and click "Run workflow"

2. **Create Release**:
   - Go to Actions → Release Workflow
   - Click "Run workflow"
   - Select version bump type or specific version
   - Click "Run workflow"

## Troubleshooting

### Common Issues

- **Tests failing**: Run `pytest -v` for detailed output
- **Version conflicts**: Check `pyproject.toml` and `CHANGELOG.md`
- **Publishing issues**: Verify PyPI token in repository secrets

## Getting Help

For more detailed information, see the full [CI/CD Documentation](CI_CD_WORKFLOW.md).

For additional support, please open an issue in the repository.
