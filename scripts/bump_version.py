#!/usr/bin/env python3
"""
Script to handle version bumping and changelog updates.

This script automates the process of:
1. Bumping the version in pyproject.toml
2. Updating the CHANGELOG.md with the new version
3. Creating a git tag
4. Pushing changes to the remote repository
"""

import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import tomli
import click

# Paths
ROOT_DIR = Path(__file__).parent.parent
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
CHANGELOG_PATH = ROOT_DIR / "CHANGELOG.md"


def get_current_version() -> str:
    """Get the current version from pyproject.toml."""
    with open(PYPROJECT_PATH, "rb") as f:
        pyproject = tomli.load(f)
    return pyproject["project"]["version"]


def bump_version(version: str, bump_type: str) -> str:
    """Bump the version number based on the bump type."""
    major, minor, patch = map(int, version.split("."))
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        # Assume it's a specific version
        if not re.match(r"^\d+\.\d+\.\d+$", bump_type):
            raise ValueError(f"Invalid version format: {bump_type}")
        return bump_type


def update_pyproject_version(version: str) -> None:
    """Update the version in pyproject.toml."""
    with open(PYPROJECT_PATH, "r") as f:
        content = f.read()
    
    # Update the version using a regex that matches the version line
    content = re.sub(
        r'^version\s*=\s*"[\d.]+[\w.-]*"',
        f'version = "{version}"',
        content,
        flags=re.MULTILINE
    )
    
    with open(PYPROJECT_PATH, "w") as f:
        f.write(content)


def update_changelog(version: str) -> None:
    """Update the CHANGELOG.md with the new version section."""
    if not CHANGELOG_PATH.exists():
        return
    
    with open(CHANGELOG_PATH, "r") as f:
        content = f.read()
    
    today = datetime.now().strftime("%Y-%m-%d")
    version_header = f"## [{version}] - {today}"
    
    # Insert the new version section after the changelog header
    if "# Changelog" in content:
        new_content = content.replace(
            "# Changelog\n\n",
            f"# Changelog\n\n{version_header}\n\n### 🚀 Features\n\n### 🐛 Bug Fixes\n\n### 📚 Documentation\n\n### 🛠 Maintenance\n\n"
        )
    else:
        new_content = f"# Changelog\n\n{version_header}\n\n### 🚀 Features\n\n### 🐛 Bug Fixes\n\n### 📚 Documentation\n\n### 🛠 Maintenance\n\n\n{content}"
    
    with open(CHANGELOG_PATH, "w") as f:
        f.write(new_content)


def git_commit_and_tag(version: str) -> None:
    """Commit changes and create a git tag."""
    subprocess.run(["git", "add", str(PYPROJECT_PATH), str(CHANGELOG_PATH)], check=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore: bump version to {version}"],
        check=True
    )
    subprocess.run(["git", "tag", f"v{version}", "-m", f"Release {version}"], check=True)


def push_changes() -> None:
    """Push changes and tags to the remote repository."""
    subprocess.run(["git", "push", "origin", "HEAD"], check=True)
    subprocess.run(["git", "push", "origin", "--tags"], check=True)


@click.command()
@click.argument("bump_type", type=click.Choice(["major", "minor", "patch"]), default="patch")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
@click.option("--no-commit", is_flag=True, help="Skip git commit and tag")
@click.option("--no-push", is_flag=True, help="Skip pushing to remote")
def main(bump_type: str, dry_run: bool, no_commit: bool, no_push: bool) -> None:
    """Bump the version and update changelog."""
    try:
        current_version = get_current_version()
        new_version = bump_version(current_version, bump_type)
        
        print(f"Current version: {current_version}")
        print(f"New version: {new_version}")
        
        if dry_run:
            print("\nThis is a dry run. No changes will be made.")
            return
        
        # Update files
        update_pyproject_version(new_version)
        update_changelog(new_version)
        
        if not no_commit:
            git_commit_and_tag(new_version)
            
            if not no_push:
                push_changes()
        
        print(f"\n✅ Successfully bumped version to {new_version}")
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
