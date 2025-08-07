#!/usr/bin/env python3
"""EVOSEAL Version Management Tool

Consolidated version management for EVOSEAL project.
Replaces bump_version.py and update_version.sh.
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import tomli
import tomli_w

# Project paths
ROOT_DIR = Path(__file__).parent.parent
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
CHANGELOG_PATH = ROOT_DIR / "CHANGELOG.md"
VERSION_FILE = ROOT_DIR / "evoseal" / "__init__.py"

# ANSI colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color


def print_status(msg: str) -> None:
    print(f"{BLUE}[INFO]{NC} {msg}")


def print_success(msg: str) -> None:
    print(f"{GREEN}[SUCCESS]{NC} {msg}")


def print_error(msg: str) -> None:
    print(f"{RED}[ERROR]{NC} {msg}", file=sys.stderr)
    sys.exit(1)


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str]:
    try:
        result = subprocess.run(
            cmd, cwd=cwd or ROOT_DIR, capture_output=True, text=True, check=False
        )
        return result.returncode, result.stdout.strip()
    except Exception as e:
        return 1, str(e)


def get_current_version() -> str:
    try:
        with open(PYPROJECT_PATH, "rb") as f:
            return tomli.load(f)["project"]["version"]
    except Exception as e:
        print_error(f"Failed to get version: {e}")


def bump_version(version: str, bump_type: str) -> str:
    try:
        major, minor, patch = map(int, version.split("."))
        if bump_type == "major":
            return f"{major+1}.0.0"
        elif bump_type == "minor":
            return f"{major}.{minor+1}.0"
        elif bump_type == "patch":
            return f"{major}.{minor}.{patch+1}"
        elif re.match(r"^\d+\.\d+\.\d+$", bump_type):
            return bump_type
        raise ValueError(f"Invalid version: {bump_type}")
    except Exception as e:
        print_error(f"Version bump failed: {e}")


def update_pyproject(version: str) -> None:
    try:
        with open(PYPROJECT_PATH, "rb") as f:
            pyproject = tomli.load(f)
        pyproject["project"]["version"] = version
        with open(PYPROJECT_PATH, "wb") as f:
            tomli_w.dump(pyproject, f)
        print_success(f"Updated pyproject.toml to {version}")
    except Exception as e:
        print_error(f"Failed to update pyproject.toml: {e}")


def update_changelog(version: str) -> None:
    try:
        date = datetime.now().strftime("%Y-%m-%d")
        content = CHANGELOG_PATH.read_text() if CHANGELOG_PATH.exists() else "# Changelog\n\n"
        new_section = f"## [{version}] - {date}\n\n* Initial release\n\n"
        updated = content.replace("# Changelog\n", f"# Changelog\n\n{new_section}", 1)
        CHANGELOG_PATH.write_text(updated)
        print_success(f"Updated CHANGELOG.md for {version}")
    except Exception as e:
        print_error(f"Failed to update CHANGELOG.md: {e}")


def git_commit_and_tag(version: str, message: str = "") -> None:
    try:
        run_cmd(["git", "add", str(PYPROJECT_PATH), str(CHANGELOG_PATH), str(VERSION_FILE)])
        msg = message or f"Bump version to {version}"
        run_cmd(["git", "commit", "-m", msg])
        run_cmd(["git", "tag", "-a", f"v{version}", "-m", f"Version {version}"])
        print_success(f"Created git tag v{version}")
    except Exception as e:
        print_error(f"Git operation failed: {e}")


def push_changes() -> None:
    try:
        run_cmd(["git", "push"])
        run_cmd(["git", "push", "--tags"])
        print_success("Pushed changes and tags to remote")
    except Exception as e:
        print_error(f"Failed to push: {e}")


def handle_bump(args) -> None:
    current = get_current_version()
    new_version = bump_version(current, args.bump_type)

    if args.dry_run:
        print(f"Would update from {current} to {new_version}")
        return

    update_pyproject(new_version)
    update_changelog(new_version)

    if not args.no_commit:
        git_commit_and_tag(new_version, args.message)
        if args.push:
            push_changes()

    print_success(f"Updated to version {new_version}")


def handle_update(args) -> None:
    if not re.match(r"^\d+\.\d+\.\d+$", args.version):
        print_error("Version must be X.Y.Z")

    if args.dry_run:
        print(f"Would update to {args.version}")
        return

    update_pyproject(args.version)
    update_changelog(args.version)

    if not args.no_commit:
        git_commit_and_tag(args.version, args.message)
        if args.push:
            push_changes()

    print_success(f"Updated to version {args.version}")


def main():
    parser = argparse.ArgumentParser(description="EVOSEAL Version Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Bump command
    bump = subparsers.add_parser("bump", help="Bump version")
    bump.add_argument("bump_type", choices=["major", "minor", "patch"])
    bump.add_argument("--dry-run", action="store_true")
    bump.add_argument("--no-commit", action="store_true")
    bump.add_argument("--push", action="store_true")
    bump.add_argument("-m", "--message", default="")
    bump.set_defaults(func=handle_bump)

    # Update command
    update = subparsers.add_parser("update", help="Set specific version")
    update.add_argument("version")
    update.add_argument("--dry-run", action="store_true")
    update.add_argument("--no-commit", action="store_true")
    update.add_argument("--push", action="store_true")
    update.add_argument("-m", "--message", default="")
    update.set_defaults(func=handle_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
