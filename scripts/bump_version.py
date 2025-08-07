#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by scripts/lib/version/version.py
Please update your workflows to use the new version management system:
  ./scripts/evoseal version --help

This script is kept for backward compatibility and will be removed in a future release.
"""

import sys


def main():
    print("\n" + "=" * 80)
    print("DEPRECATION WARNING: This script has been replaced by scripts/lib/version/version.py")
    print("Please update your workflows to use the new version management system:")
    print("  ./scripts/evoseal version --help\n")
    print("To continue using this script, you can run:")
    print(f"  python3 {__file__} --force <major|minor|patch|version>")
    print("=" * 80 + "\n")

    if "--force" not in sys.argv:
        sys.exit(1)

    # Remove --force flag and continue with original script
    sys.argv.remove("--force")

    # Original script functionality follows...
    import re
    import subprocess
    from pathlib import Path
    from typing import Optional, Tuple

    def get_current_version() -> str:
        """Get the current version from pyproject.toml."""
        pyproject = Path("pyproject.toml")
        if not pyproject.exists():
            print("Error: pyproject.toml not found", file=sys.stderr)
            sys.exit(1)

        version_pattern = re.compile(r'^version\s*=\s*["\'](\d+\.\d+\.\d+)["\']\s*$', re.MULTILINE)
        content = pyproject.read_text()

        match = version_pattern.search(content)
        if not match:
            print("Error: Could not find version in pyproject.toml", file=sys.stderr)
            sys.exit(1)

        return match.group(1)

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
            if not re.match(r'^\d+\.\d+\.\d+$', bump_type):
                print(f"Error: Invalid version format: {bump_type}", file=sys.stderr)
                print("Version must be in format MAJOR.MINOR.PATCH or one of: major, minor, patch", file=sys.stderr)
                sys.exit(1)
            return bump_type

    def update_pyproject(version: str) -> None:
        """Update the version in pyproject.toml."""
        pyproject = Path("pyproject.toml")
        content = pyproject.read_text()

        # Update version in pyproject.toml
        new_content = re.sub(
            r'^(version\s*=\s*["\']).*?(["\']\s*)$',
            f'\\g<1>{version}\\g<2>',
            content,
            flags=re.MULTILINE,
            count=1
        )

        if new_content == content:
            print("Warning: Version not updated in pyproject.toml - version string not found", file=sys.stderr)
        else:
            pyproject.write_text(new_content)
            print(f"Updated pyproject.toml to version {version}")

    def update_changelog(version: str) -> None:
        """Update the changelog with the new version."""
        changelog = Path("CHANGELOG.md")
        if not changelog.exists():
            print("Warning: CHANGELOG.md not found - skipping changelog update", file=sys.stderr)
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
