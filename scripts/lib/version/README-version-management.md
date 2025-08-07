# EVOSEAL Version Management

This directory contains scripts for managing EVOSEAL's versioning and release process.

## New Unified Version Management

As of August 2025, we've consolidated multiple version management scripts into a single, more powerful tool:

### `version.py`

A unified Python script that handles all version management tasks.

#### Features:
- Bump version numbers (major, minor, patch)
- Set specific versions
- Update changelog
- Create git tags
- Push changes to remote
- Dry-run mode

#### Usage:

```bash
# Bump version (major/minor/patch)
python scripts/version.py bump [major|minor|patch] [options]

# Set specific version
python scripts/version.py update X.Y.Z [options]

# Options:
#   --dry-run    Show what would be done without making changes
#   --no-commit  Skip creating git commit and tag
#   --push       Push changes to remote repository
#   -m, --message  Custom commit message
```

#### Examples:

```bash
# Bump patch version and push
python scripts/version.py bump patch --push

# Set specific version with custom message
python scripts/version.py update 1.2.3 -m "Release version 1.2.3"

# See what would happen without making changes
python scripts/version.py bump minor --dry-run
```

## Deprecated Scripts

The following scripts have been deprecated in favor of `version.py`:

- `bump_version.py` - Use `version.py bump`
- `update_version.sh` - Use `version.py update`

## Version File Locations

The version number is maintained in these files:
- `pyproject.toml` - Main version reference
- `CHANGELOG.md` - Release history
- `evoseal/__init__.py` - Python package version

## Release Process

1. Bump version:
   ```bash
   python scripts/version.py bump minor --push
   ```

2. Create release notes in `CHANGELOG.md`

3. Push changes and tags:
   ```bash
   git push
   git push --tags
   ```

4. Create a GitHub release with the new tag

## Troubleshooting

If you encounter permission issues, make the script executable:
```bash
chmod +x scripts/version.py
```

For other issues, run with `--dry-run` first to see what would be changed.
