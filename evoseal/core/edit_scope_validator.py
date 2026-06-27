"""
Edit-scope allowlist validator for EVOSEAL evolution pipeline.

This module enforces a path allowlist before any generated edit is written to disk,
preventing self-modifications from targeting safety-critical files.

See threat model §3 and Plans.md task 2.13 for requirements.
"""

from pathlib import Path


class EditScopeError(Exception):
    """Raised when an edit violates the scope allowlist."""

    pass


class EditScopeValidator:
    """Enforces an immutable edit-scope allowlist.

    This validator rejects edits targeting safety-critical files and anything
    outside the declared mutable surface. The allowlist is itself immutable
    (not editable by the evolution loop).

    Forbidden paths (always rejected):
    - configs/safety.yaml (immutable safety configuration)
    - .env (secrets file)
    - Makefile (build configuration)
    - .github/workflows/ (CI configuration)
    - .git/ (repository state)
    - Anything outside the repo root
    - Any symlinks to forbidden targets

    Allowed paths (mutable surface):
    - evoseal/ (main package)
    - tests/ (test infrastructure)
    - examples/ (example code)
    - docs/ (documentation, except safety config docs reference)
    """

    def __init__(self) -> None:
        """Initialize the validator with immutable default allowlist."""
        # Forbidden paths: these are always rejected
        self._forbidden_paths: set[str] = {
            "configs/safety.yaml",
            ".env",
            "Makefile",
        }

        # Forbidden directories: these and their contents are rejected
        self._forbidden_dirs: set[str] = {
            ".git",
            ".github/workflows",
            ".evoseal",
            ".pytest_cache",
            "__pycache__",
            ".venv",
            "venv",
        }

        # Allowed patterns: only files under these directories can be edited
        self._allowed_patterns: set[str] = {
            "evoseal/",
            "tests/",
            "examples/",
            "docs/",
            "scripts/",
            "benchmarks/",
            "config/",  # mutable config files (not configs/safety.yaml)
        }

    @property
    def forbidden_paths(self) -> set[str]:
        """Get forbidden file paths (read-only)."""
        return self._forbidden_paths.copy()

    @property
    def forbidden_dirs(self) -> set[str]:
        """Get forbidden directories (read-only)."""
        return self._forbidden_dirs.copy()

    @property
    def allowed_patterns(self) -> set[str]:
        """Get allowed path patterns (read-only)."""
        return self._allowed_patterns.copy()

    def validate_edit_path(self, file_path: str, repo_root: Path) -> None:
        """Validate that a file edit is within the allowed scope.

        Args:
            file_path: Absolute path to the file being edited
            repo_root: Root directory of the repository

        Raises:
            EditScopeError: If the path is forbidden or outside the repo
            ValueError: If the path is invalid or a symlink attack is detected
        """
        # Normalize paths
        file_path_obj = self._resolve_and_normalize(file_path)
        repo_root_obj = Path(repo_root).resolve()

        # Check for symlink attacks
        self._check_symlink_attack(file_path_obj)

        # Check if path is within repo root
        try:
            rel_path = file_path_obj.relative_to(repo_root_obj)
        except ValueError as e:
            raise EditScopeError(
                f"Edit path {file_path} is outside repo root {repo_root}. "
                "Edits must target files within the repository scope."
            ) from e

        rel_path_str = str(rel_path)

        # Check against forbidden files
        if rel_path_str in self._forbidden_paths:
            raise EditScopeError(
                f"Edit to {rel_path_str} is forbidden. "
                f"This file defines immutable safety or build configuration."
            )

        # Check against forbidden directories
        for forbidden_dir in self._forbidden_dirs:
            if rel_path_str.startswith(forbidden_dir + "/") or rel_path_str == forbidden_dir:
                raise EditScopeError(
                    f"Edit to {rel_path_str} is forbidden. "
                    f"Directory {forbidden_dir}/ is protected from modification."
                )

        # Check against allowed patterns
        is_allowed = False
        for allowed_pattern in self._allowed_patterns:
            if rel_path_str.startswith(allowed_pattern):
                is_allowed = True
                break

        if not is_allowed:
            raise EditScopeError(
                f"Edit to {rel_path_str} is outside the mutable surface. "
                f"Allowed patterns: {', '.join(sorted(self._allowed_patterns))}. "
                f"Generated code can only modify files in these directories."
            )

    def _resolve_and_normalize(self, file_path: str) -> Path:
        """Resolve and normalize a file path.

        Args:
            file_path: Path to resolve (may be relative or absolute)

        Returns:
            Resolved and normalized Path object

        Raises:
            ValueError: If path cannot be resolved
        """
        try:
            path_obj = Path(file_path).resolve()
            return path_obj
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Cannot resolve path {file_path}: {e}") from e

    def _check_symlink_attack(self, file_path: Path) -> None:
        """Check for symlink attacks (symlink to forbidden file).

        Args:
            file_path: Path to check

        Raises:
            EditScopeError: If a symlink to a forbidden target is detected
        """
        # Walk up the path and check each component for symlinks
        current = Path("/")
        for part in file_path.parts[1:]:  # Skip the root "/"
            current = current / part

            if current.is_symlink():
                target = current.resolve()

                # Check if symlink target is in a forbidden directory
                for forbidden_dir in self._forbidden_dirs:
                    forbidden_path = Path(forbidden_dir)
                    try:
                        target.relative_to(forbidden_path)
                        raise EditScopeError(
                            f"Symlink attack detected: {file_path} -> {target}. "
                            f"Symlinks to forbidden directories are not allowed."
                        )
                    except ValueError:
                        pass  # Not under this forbidden dir, continue checking

                # Check if symlink target is a forbidden file
                for forbidden_file in self._forbidden_paths:
                    if str(target).endswith(forbidden_file):
                        raise EditScopeError(
                            f"Symlink attack detected: {file_path} -> {target}. "
                            f"Symlinks to forbidden files are not allowed."
                        )
