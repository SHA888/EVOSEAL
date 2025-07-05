"""
Git-Compatible Storage Utilities for EVOSEAL

Provides functions and a class to store and retrieve model data in a Git repository structure,
with support for versioning, diffs, merges, and querying by Git references (branches, tags, commits).
"""

import json
import os
import shutil
import subprocess  # nosec - Required for git operations, with proper input validation
from pathlib import Path
from typing import Any, Optional, Union


class GitStorageError(Exception):
    pass


class GitStorage:
    def __init__(self, repo_path: Union[str, Path]) -> None:
        self.repo_path = Path(repo_path)
        if not (self.repo_path / ".git").exists():
            raise GitStorageError(f"Not a git repository: {self.repo_path}")

    def _run_git(
        self,
        args: list[str],
        capture_output: bool = True,
        check: bool = True,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess:
        """Run a git command with security best practices.

        Args:
            args: Git command arguments (e.g., ["commit", "-m", "message"])
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise CalledProcessError on non-zero exit code
            **kwargs: Additional arguments to subprocess.run()

        Returns:
            subprocess.CompletedProcess

        Raises:
            GitStorageError: If command fails and check=True
            ValueError: If args contain suspicious patterns
        """
        # Validate git command arguments
        for arg in args:
            if not isinstance(arg, str):
                raise ValueError(f"Git command arguments must be strings, got {type(arg)}")
            if ";" in arg or "`" in arg or "&&" in arg:
                raise ValueError(f"Potentially dangerous characters in git argument: {arg}")

        # Use shutil.which to safely find the git executable
        git_path = shutil.which("git")
        if not git_path:
            raise GitStorageError("Git executable not found in PATH")

        try:
            # Ensure args are strings and don't contain command separators
            safe_args = [str(arg) for arg in args]

            result = subprocess.run(  # nosec - Inputs are validated and shell=False
                [git_path] + safe_args,  # Use list concatenation for safety
                cwd=str(self.repo_path.absolute()),
                capture_output=capture_output,
                text=True,
                check=check,
                shell=False,  # Prevent shell injection
                **{k: v for k, v in kwargs.items() if k != "shell"},  # Force shell=False
            )
            return result
        except subprocess.CalledProcessError as e:
            raise GitStorageError(f"Git command failed: {e.stderr or e}") from e
        except FileNotFoundError as e:
            raise GitStorageError("Git executable not found") from e

    def save_model(
        self, model: Any, rel_path: str, message: str, branch: Optional[str] = None
    ) -> str:
        """Save a model (as JSON) to the repo and commit it. Optionally on a branch."""
        file_path = self.repo_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(model, f, indent=2)
        self._run_git(["add", rel_path])
        if branch:
            # Check if branch exists
            branches = self.list_refs()["branches"]
            if branch not in branches:
                self._run_git(["checkout", "-b", branch])
            else:
                self._run_git(["checkout", branch])
        else:
            # Default to master if exists, else stay on current branch
            branches = self.list_refs()["branches"]
            if "master" in branches:
                self._run_git(["checkout", "master"])
        self._run_git(["commit", "-m", message])
        commit_hash = self._run_git(["rev-parse", "HEAD"]).stdout.strip()
        return str(commit_hash)

    def load_model(self, rel_path: str, ref: Optional[str] = None) -> dict[str, Any]:
        """Load a model file (JSON) from the repo at a given ref (branch/tag/commit)."""
        if ref:
            args = ["show", f"{ref}:{rel_path}"]
        else:
            args = ["show", f"HEAD:{rel_path}"]
        try:
            result = self._run_git(args)
        except subprocess.CalledProcessError as e:
            if "fatal: Path" in (e.stderr or ""):
                raise FileNotFoundError(f"File not found at {ref or 'HEAD'}:{rel_path}") from e
            raise
        return dict(json.loads(result.stdout))

    def list_versions(self, rel_path: str) -> list[str]:
        """List commit hashes for the given file."""
        result = self._run_git(["log", "--pretty=format:%H", "--", rel_path])
        return [line.strip() for line in result.stdout.strip().splitlines()]

    def get_diff(self, rel_path: str, ref_a: str, ref_b: str) -> str:
        """Get the diff of a file between two refs."""
        result = self._run_git(["diff", f"{ref_a}:{rel_path}", f"{ref_b}:{rel_path}"])
        return str(result.stdout)

    def merge_model(self, rel_path: str, source_ref: str, target_ref: str) -> str:
        """Merge changes from source_ref into target_ref (merges all changes, not just a file)."""
        # Checkout target_ref
        self._run_git(["checkout", target_ref])
        # Merge source_ref (merge all changes)
        self._run_git(["merge", source_ref])
        commit_hash = self._run_git(["rev-parse", "HEAD"]).stdout.strip()
        return str(commit_hash)

    def get_file_at_commit(self, rel_path: str, commit_hash: str) -> dict[str, Any]:
        """Get file contents at a specific commit."""
        result = self._run_git(["show", f"{commit_hash}:{rel_path}"])
        return dict(json.loads(result.stdout))

    def list_refs(self) -> dict[str, list[str]]:
        """List branches and tags in the repo."""
        branches = self._run_git(["branch", "--list"]).stdout.strip().splitlines()
        tags = self._run_git(["tag", "--list"]).stdout.strip().splitlines()
        clean_branches = [b.strip().replace("*", "").strip() for b in branches if b.strip()]
        clean_tags = [t.strip() for t in tags if t.strip()]
        return {"branches": clean_branches, "tags": clean_tags}
