"""
Command-line Git implementation for GitInterface.

This module provides an implementation of GitInterface using the git command-line tool.
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .git_interface import GitInterface, GitOperation, GitResult


class CmdGit(GitInterface):
    """
    Implementation of GitInterface using the git command-line tool.
    """

    def __init__(self, repo_path: Optional[Union[str, Path]] = None):
        """
        Initialize the CmdGit instance.

        Args:
            repo_path: Path to the Git repository (optional)
        """
        super().__init__(repo_path)
        self._initialized = False

        # Only check if the repository is initialized if a path is provided
        # but don't require it to be initialized yet
        if repo_path and os.path.exists(os.path.join(repo_path, '.git')):
            self._initialized = True

    def initialize(
        self, repo_url: Optional[str] = None, clone_path: Optional[Union[str, Path]] = None
    ) -> 'CmdGit':
        """
        Initialize the Git repository.

        If repo_url is provided, clone the repository. Otherwise, initialize a new one.

        Args:
            repo_url: URL of the repository to clone (optional)
            clone_path: Path where to clone the repository (required if repo_url is provided)

        Returns:
            Self for method chaining
        """
        if repo_url:
            if not clone_path:
                raise ValueError("clone_path is required when repo_url is provided")
            return self.clone(repo_url, clone_path)

        if not self.repo_path:
            raise ValueError("repo_path must be set when initializing a new repository")

        if not (self.repo_path / ".git").exists():
            success, stdout, stderr = self._run_git_command(["init"])
            if not success:
                raise RuntimeError(f"Failed to initialize Git repository: {stderr}")

        self._initialized = True
        return self

    def is_initialized(self) -> bool:
        """Check if the Git repository is properly initialized."""
        if not self.repo_path:
            return False
        return (self.repo_path / ".git").exists()

    def clone(self, repo_url: str, target_path: Optional[Union[str, Path]] = None) -> 'CmdGit':
        """
        Clone a Git repository.

        Args:
            repo_url: URL of the repository to clone
            target_path: Path where to clone the repository

        Returns:
            Self for method chaining
        """
        if not target_path:
            # Extract repo name from URL if target_path not provided
            repo_name = repo_url.split("/")[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            target_path = Path.cwd() / repo_name
        else:
            target_path = Path(target_path)

        # Create parent directory if it doesn't exist
        target_path.parent.mkdir(parents=True, exist_ok=True)

        success, stdout, stderr = self._run_git_command(["clone", repo_url, str(target_path)])
        if not success:
            raise RuntimeError(f"Failed to clone repository: {stderr}")

        self.repo_path = target_path
        self._initialized = True
        return self

    def pull(self, remote: str = "origin", branch: str = "main") -> GitResult:
        """
        Pull changes from a remote repository.

        Args:
            remote: Name of the remote (default: 'origin')
            branch: Name of the branch to pull (default: 'main')

        Returns:
            GitResult with the operation result
        """
        self._check_initialized()
        success, stdout, stderr = self._run_git_command(["pull", remote, branch])
        return GitResult(success, stdout, stderr if not success else None)

    def push(self, remote: str = "origin", branch: str = "main", force: bool = False) -> GitResult:
        """
        Push changes to a remote repository.

        Args:
            remote: Name of the remote (default: 'origin')
            branch: Name of the branch to push (default: 'main')
            force: Whether to force push (default: False)

        Returns:
            GitResult with the operation result
        """
        self._check_initialized()
        cmd = ["push"]
        if force:
            cmd.append("--force")
        cmd.extend([remote, branch])

        success, stdout, stderr = self._run_git_command(cmd)
        return GitResult(success, stdout, stderr if not success else None)

    def commit(self, message: str, files: Optional[List[Union[str, Path]]] = None) -> GitResult:
        """
        Commit changes to the repository.

        Args:
            message: Commit message
            files: List of files to include in the commit (all if None)

        Returns:
            GitResult with the operation result
        """
        self._check_initialized()

        # Stage files if specified
        if files:
            file_paths = [str(f) for f in files]
            success, stdout, stderr = self._run_git_command(["add"] + file_paths)
            if not success:
                return GitResult(False, stdout, stderr)
        else:
            # Stage all changes
            success, stdout, stderr = self._run_git_command(["add", "."])
            if not success:
                return GitResult(False, stdout, stderr)

        # Create commit
        success, stdout, stderr = self._run_git_command(["commit", "-m", message])
        return GitResult(success, stdout, stderr if not success else None)

    def checkout(self, branch: str, create: bool = False) -> GitResult:
        """
        Checkout a branch.

        Args:
            branch: Name of the branch to checkout
            create: Whether to create the branch if it doesn't exist (default: False)

        Returns:
            GitResult with the operation result
        """
        self._check_initialized()

        cmd = ["checkout"]
        if create:
            cmd.append("-b")
        cmd.append(branch)

        success, stdout, stderr = self._run_git_command(cmd)
        return GitResult(success, stdout, stderr if not success else None)

    def status(self) -> GitResult:
        """
        Get the status of the repository.

        Returns:
            GitResult with status information
        """
        self._check_initialized()
        success, stdout, stderr = self._run_git_command(["status"])
        return GitResult(success, stdout, stderr if not success else None)

    def diff(self, staged: bool = False) -> GitResult:
        """
        Get the diff of the repository.

        Args:
            staged: Whether to show staged changes (default: False)

        Returns:
            GitResult with diff information
        """
        self._check_initialized()
        cmd = ["diff"]
        if staged:
            cmd.append("--cached")

        success, stdout, stderr = self._run_git_command(cmd)
        return GitResult(success, stdout, stderr if not success else None)

    def log(self, n: int = 10) -> GitResult:
        """
        Get the commit log.

        Args:
            n: Number of commits to show (default: 10)

        Returns:
            GitResult with log information
        """
        self._check_initialized()
        success, stdout, stderr = self._run_git_command(["log", f"-{n}", "--oneline"])
        return GitResult(success, stdout, stderr if not success else None)

    def branch(self, name: Optional[str] = None, delete: bool = False) -> GitResult:
        """
        List, create, or delete branches.

        Args:
            name: Name of the branch to create or delete
            delete: Whether to delete the branch (default: False)

        Returns:
            GitResult with branch information
        """
        self._check_initialized()

        if name is None:
            # List branches
            success, stdout, stderr = self._run_git_command(["branch", "--list"])
        else:
            if delete:
                # Delete branch
                success, stdout, stderr = self._run_git_command(["branch", "-D", name])
            else:
                # Create branch
                success, stdout, stderr = self._run_git_command(["branch", name])

        return GitResult(success, stdout, stderr if not success else None)

    def tag(
        self, name: Optional[str] = None, message: Optional[str] = None, delete: bool = False
    ) -> GitResult:
        """
        List, create, or delete tags.

        Args:
            name: Name of the tag to create or delete
            message: Tag message (for annotated tags)
            delete: Whether to delete the tag (default: False)

        Returns:
            GitResult with tag information
        """
        self._check_initialized()

        if name is None:
            # List tags
            success, stdout, stderr = self._run_git_command(["tag", "-l"])
        else:
            if delete:
                # Delete tag
                success, stdout, stderr = self._run_git_command(["tag", "-d", name])
            else:
                # Create tag
                if message:
                    success, stdout, stderr = self._run_git_command(
                        ["tag", "-a", name, "-m", message]
                    )
                else:
                    success, stdout, stderr = self._run_git_command(["tag", name])

        return GitResult(success, stdout, stderr if not success else None)

    def get_file_content(self, file_path: Union[str, Path]) -> Optional[str]:
        """
        Get the content of a file from the repository.

        Args:
            file_path: Path to the file (relative to repo root)

        Returns:
            File content as string, or None if file doesn't exist
        """
        self._check_initialized()

        full_path = self.repo_path / file_path
        if not full_path.exists():
            return None

        try:
            return full_path.read_text(encoding='utf-8')
        except Exception as e:
            return None

    def write_file_content(self, file_path: Union[str, Path], content: str) -> bool:
        """
        Write content to a file in the repository.

        Args:
            file_path: Path to the file (relative to repo root)
            content: Content to write to the file

        Returns:
            True if successful, False otherwise
        """
        self._check_initialized()

        full_path = self.repo_path / file_path

        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            full_path.write_text(content, encoding='utf-8')
            return True
        except Exception as e:
            return False

    def get_repository_structure(self) -> Dict[str, Any]:
        """
        Get the structure of the repository as a nested dictionary.

        Returns:
            Nested dictionary representing the repository structure
        """
        self._check_initialized()

        def _get_structure(path: Path) -> Dict[str, Any]:
            """Recursively get the directory structure."""
            if not path.exists() or not path.is_dir():
                return {}

            structure = {}
            for item in path.iterdir():
                if item.name == '.git':
                    continue

                if item.is_dir():
                    structure[item.name] = _get_structure(item)
                else:
                    structure[item.name] = None

            return structure

        return _get_structure(self.repo_path)

    def _check_initialized(self) -> None:
        """Check if the repository is initialized, raise an exception if not."""
        if not self.repo_path or not self.is_initialized():
            raise RuntimeError("Git repository is not initialized. Call initialize() first.")
