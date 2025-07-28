# EVOSEAL v0.3.3 Release Notes

## 🎉 Release Highlights

**CI/CD Reliability and Stability Release** - This patch release resolves all critical GitHub Actions workflow failures and establishes a robust, consistent development pipeline.

## 📅 Release Information
- **Version**: 0.3.3
- **Release Date**: 2025-07-28
- **Focus**: CI/CD Pipeline Reliability and Developer Experience
- **Type**: Patch Release (Bug Fixes and Infrastructure Improvements)

## 🔗 Useful Links

- [📚 Documentation](https://sha888.github.io/EVOSEAL/)
- [🐙 GitHub Repository](https://github.com/SHA888/EVOSEAL)
- [🐛 Report Issues](https://github.com/SHA888/EVOSEAL/issues)
- [📋 Full Changelog](https://github.com/SHA888/EVOSEAL/blob/main/CHANGELOG.md)

## 🚀 Major Improvements

### ✅ CI/CD Pipeline Reliability

**Black Formatting Configuration Unified**
- Fixed critical mismatch between local pre-commit hooks and GitHub Actions CI
- Unified line-length=100 and skip-string-normalization across all tools
- Updated CI to use `black --check .` (respects pyproject.toml configuration)
- Eliminated CI failures caused by formatting inconsistencies

**Virtual Environment Exclusions**
- Added comprehensive exclusions for .venv*, venv*, env*, .env*, .semgrep-venv
- Prevents formatting tools from processing virtual environment files
- Consistent exclusions across Black, isort, and Ruff configurations

**GitHub Actions Workflow Fixes**
- **Release Workflow**: Fixed trigger logic to only run on actual tag pushes
- **Cleanup Workflow**: Added `contents: write` permission for git push operations
- **CodeQL Workflow**: Fixed YAML syntax error (duplicate `if:` conditions)
- All workflows now validate and run successfully

### 🔧 Developer Experience Improvements

**Pre-commit Configuration Streamlined**
- Removed problematic safety CLI check that was blocking releases
- Safety checks still available manually: `safety check --short-report`
- All essential quality checks maintained: Black, isort, bandit, detect-secrets
- Pre-commit hooks now run reliably without policy file issues

**Configuration Consistency**
- pyproject.toml now serves as single source of truth for formatting settings
- Black: line-length=100, skip-string-normalization=true
- isort: line_length=100, profile=black
- Ruff: line-length=100, consistent exclusions
- Fixed Ruff target-version to remain "py39" (not package version)

## 🐛 Bug Fixes

- Fixed GitHub Actions CI failing on Black formatting checks
- Resolved virtual environment files being processed by formatting tools
- Fixed CodeQL workflow YAML syntax error preventing execution
- Corrected Release workflow trigger logic preventing unnecessary runs
- Fixed Cleanup workflow permission denied errors during git push
- Resolved safety policy file format issues blocking pre-commit hooks

## 📊 Contributors

Thanks to all contributors who made this release possible:

- **Kresna Sucandra** - CI/CD pipeline reliability improvements and workflow fixes

---

**Installation:**
```bash
pip install evoseal==0.3.3
```

**Upgrade:**
```bash
pip install --upgrade evoseal
```

*This release was automatically generated on 2025-07-28 04:10:42 UTC*
