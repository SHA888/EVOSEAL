"""
Version Manager for EVOSEAL

This module provides a high-level interface for version control operations,
building on top of the GitInterface implementation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .config import default_git_implementation
from .git_interface import GitInterface, GitResult

logger = logging.getLogger(__name__)


@dataclass
class CommitInfo:
    """Data class representing commit information."""

    hash: str
    author: str
    date: datetime
    message: str
    files_changed: List[str] = field(default_factory=list)


@dataclass
class BranchInfo:
    """Data class representing branch information."""

    name: str
    is_current: bool = False
    is_remote: bool = False
    upstream: Optional[str] = None
    last_commit_hash: Optional[str] = None
    last_commit_message: Optional[str] = None


class VersionManager:
    """
    High-level version control manager that provides a simplified interface
    for common version control operations.
    """

    def __init__(self, repo_path: Union[str, Path], git_implementation=None):
        """
        Initialize the VersionManager.

        Args:
            repo_path: Path to the repository
            git_implementation: GitInterface implementation to use (defaults to CmdGit)
        """
        self.repo_path = Path(repo_path).expanduser().resolve()
        self.git = git_implementation or default_git_implementation(self.repo_path)

        if not self.git.is_initialized():
            logger.warning(f"Git repository not initialized at {self.repo_path}")

    # Repository operations
    def initialize_repository(self, bare: bool = False) -> bool:
        """
        Initialize a new Git repository.

        Args:
            bare: Whether to create a bare repository

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.git.initialize()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize repository: {e}")
            return False

    def clone_repository(
        self, repo_url: str, target_path: Optional[Union[str, Path]] = None
    ) -> bool:
        """
        Clone a remote repository.

        Args:
            repo_url: URL of the repository to clone
            target_path: Path where to clone the repository (defaults to repo name)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.git = self.git.clone(repo_url, target_path)
            self.repo_path = self.git.repo_path
            return True
        except Exception as e:
            logger.error(f"Failed to clone repository: {e}")
            return False

    # Branch operations
    def get_current_branch(self) -> Optional[str]:
        """
        Get the name of the current branch.

        Returns:
            str: Name of the current branch, or None if not in a Git repository
        """
        result = self.git.branch()
        if not result.success:
            return None

        for line in result.output.splitlines():
            if line.startswith('*'):
                return line[2:].strip()
        return None

    def list_branches(self, include_remote: bool = False) -> List[BranchInfo]:
        """
        List all branches.

        Args:
            include_remote: Whether to include remote branches

        Returns:
            List[BranchInfo]: List of branch information objects
        """
        result = self.git.branch()
        if not result.success:
            return []

        branches = []
        current_branch = None

        # Get current branch
        for line in result.output.splitlines():
            if line.startswith('*'):
                current_branch = line[2:].strip()
                branches.append(BranchInfo(name=current_branch, is_current=True))
            else:
                branches.append(BranchInfo(name=line.strip()))

        # Get remote branches if requested
        if include_remote:
            remote_result = self.git.branch("-r")
            if remote_result.success:
                for line in remote_result.output.splitlines():
                    branch_name = line.strip()
                    if ' -> ' not in branch_name:  # Skip HEAD -> refs/...
                        branches.append(BranchInfo(name=branch_name, is_remote=True))

        return branches

    def create_branch(self, name: str, checkout: bool = False) -> bool:
        """
        Create a new branch.

        Args:
            name: Name of the new branch
            checkout: Whether to checkout the new branch

        Returns:
            bool: True if successful, False otherwise
        """
        result = self.git.branch(name)
        if not result.success:
            return False

        if checkout:
            return self.checkout_branch(name)

        return True

    def checkout_branch(self, name: str, create: bool = False) -> bool:
        """
        Checkout a branch.

        Args:
            name: Name of the branch to checkout
            create: Whether to create the branch if it doesn't exist

        Returns:
            bool: True if successful, False otherwise
        """
        result = self.git.checkout(name, create=create)
        return result.success

    # Commit operations
    def get_commit_history(self, limit: int = 10) -> List[CommitInfo]:
        """
        Get commit history.

        Args:
            limit: Maximum number of commits to return

        Returns:
            List[CommitInfo]: List of commit information objects
        """
        result = self.git.log(n=limit)
        if not result.success:
            return []

        commits = []
        current_commit = None

        # Parse git log output
        for line in result.output.splitlines():
            if line.startswith('commit '):
                if current_commit:
                    commits.append(current_commit)
                commit_hash = line[7:]
                current_commit = CommitInfo(hash=commit_hash, author="", date=None, message="")
            elif line.startswith('Author: '):
                if current_commit:
                    current_commit.author = line[8:].strip()
            elif line.startswith('Date:   '):
                if current_commit:
                    # Parse date string (e.g., "Date:   Mon Jul 7 12:34:56 2025 +0800")
                    date_str = line[8:].strip()
                    try:
                        current_commit.date = datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y %z")
                    except ValueError:
                        logger.warning(f"Could not parse date: {date_str}")
            elif line.strip() and not line.startswith('    '):
                if current_commit:
                    current_commit.message = line.strip()

        if current_commit:
            commits.append(current_commit)

        return commits

    def create_commit(self, message: str, files: Optional[List[Union[str, Path]]] = None) -> bool:
        """
        Create a new commit.

        Args:
            message: Commit message
            files: List of files to include in the commit (all if None)

        Returns:
            bool: True if successful, False otherwise
        """
        result = self.git.commit(message, files)
        return result.success

    # File operations
    def get_file_content(
        self, file_path: Union[str, Path], revision: str = "HEAD"
    ) -> Optional[str]:
        """
        Get the content of a file at a specific revision.

        Args:
            file_path: Path to the file (relative to repo root)
            revision: Git revision (commit hash, branch, tag, etc.)

        Returns:
            str: File content, or None if file doesn't exist
        """
        if str(revision).lower() == "head":
            return self.git.get_file_content(file_path)

        # For specific revisions, we need to use git show
        result = self.git._run_git_command(["show", f"{revision}:{file_path}"])
        if result[0]:
            return result[1]
        return None

    def write_file(self, file_path: Union[str, Path], content: str) -> bool:
        """
        Write content to a file in the repository.

        Args:
            file_path: Path to the file (relative to repo root)
            content: Content to write

        Returns:
            bool: True if successful, False otherwise
        """
        return self.git.write_file_content(file_path, content)

    def get_repository_structure(self) -> Dict[str, Any]:
        """
        Get the structure of the repository.

        Returns:
            Dict representing the repository structure
        """
        return self.git.get_repository_structure()

    # Remote operations
    def add_remote(self, name: str, url: str) -> bool:
        """
        Add a remote repository.

        Args:
            name: Name of the remote
            url: URL of the remote repository

        Returns:
            bool: True if successful, False otherwise
        """
        result = self.git._run_git_command(["remote", "add", name, url])
        return result[0]

    def list_remotes(self) -> Dict[str, str]:
        """
        List all remote repositories.

        Returns:
            Dict mapping remote names to URLs
        """
        result = self.git._run_git_command(["remote", "-v"])
        remotes = {}

        if result[0]:
            for line in result[1].splitlines():
                if '\t' in line:
                    name, url = line.split('\t')
                    if '(fetch)' in url:
                        remotes[name] = url.split(' ')[0]

        return remotes

    def pull(self, remote: str = "origin", branch: str = None) -> bool:
        """
        Pull changes from a remote repository.

        Args:
            remote: Name of the remote (default: 'origin')
            branch: Name of the branch to pull (default: current branch)

        Returns:
            bool: True if successful, False otherwise
        """
        if branch is None:
            branch = self.get_current_branch()
            if branch is None:
                logger.error("Could not determine current branch")
                return False

        result = self.git.pull(remote, branch)
        return result.success

    def push(self, remote: str = "origin", branch: str = None, force: bool = False) -> bool:
        """
        Push changes to a remote repository.

        Args:
            remote: Name of the remote (default: 'origin')
            branch: Name of the branch to push (default: current branch)
            force: Whether to force push (default: False)

        Returns:
            bool: True if successful, False otherwise
        """
        if branch is None:
            branch = self.get_current_branch()
            if branch is None:
                logger.error("Could not determine current branch")
                return False

        result = self.git.push(remote, branch, force=force)
        return result.success

    # Status and diff
    def get_status(self) -> Dict[str, List[str]]:
        """
        Get the status of the working directory.

        Returns:
            Dict with keys 'staged', 'unstaged', 'untracked' containing lists of files
        """
        result = self.git.status()
        if not result.success:
            return {'staged': [], 'unstaged': [], 'untracked': []}

        status = {'staged': [], 'unstaged': [], 'untracked': []}

        current_section = None
        for line in result.output.splitlines():
            line = line.strip()
            if not line:
                continue

            if 'Changes to be committed:' in line:
                current_section = 'staged'
            elif 'Changes not staged for commit:' in line:
                current_section = 'unstaged'
            elif 'Untracked files:' in line:
                current_section = 'untracked'
            elif line == 'no changes added to commit (use "git add" and/or "git commit -a")':
                continue
            elif current_section and ':' in line:
                # Skip section headers
                continue
            elif current_section and line and not line.startswith('('):
                # Add file to current section
                # Remove status prefix (e.g., 'modified:   file.txt' -> 'file.txt')
                file_path = line.split(':', 1)[-1].strip()
                if file_path:
                    status[current_section].append(file_path)

        return status

    def get_diff(self, staged: bool = False) -> str:
        """
        Get the diff of the working directory or staging area.

        Args:
            staged: Whether to show staged changes (default: False)

        Returns:
            str: Diff output
        """
        result = self.git.diff(staged=staged)
        return result.output if result.success else ""
