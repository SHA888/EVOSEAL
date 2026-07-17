#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by scripts/lib/version/version.py
Please update your workflows to use the new version management system:
  ./scripts/evoseal version --help

This script is kept only to point callers at the replacement and will be removed
in a future release.

Note: the previous "original script functionality" block below the deprecation
notice was unreachable and syntactically invalid (an `except` with no `try`, and
calls to functions that were never defined -- update_pyproject_version,
git_commit_and_tag, push_changes). It could not run, so it has been removed
rather than left as a parse error. Use `./scripts/evoseal version` instead.
"""

import sys


def main() -> None:
    """Print the deprecation notice and exit non-zero."""
    print("\n" + "=" * 80)
    print("DEPRECATION WARNING: This script has been replaced by scripts/lib/version/version.py")
    print("Please update your workflows to use the new version management system:")
    print("  ./scripts/evoseal version --help")
    print("=" * 80 + "\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
