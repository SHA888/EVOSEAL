"""
GitInterface - Base class for Git operations in EVOSEAL

This module provides an abstract base class for Git operations with a consistent
interface that can be implemented by different backends.
"""

import logging
import os
import shutil
import subprocess  # nosec
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

# Type variable for the GitInterface class
TGitInterface = TypeVar('TGitInterface', bound='GitInterface')

logger = logging.getLogger(__name__)


class GitOperation(Enum):
    """Enum representing different Git operations."""

    CLONE = auto()
    PULL = auto()
    PUSH = auto()
    COMMIT = auto()
    CHECKOUT = auto()
    STATUS = auto()
    DIFF = auto()
    LOG = auto()
    BRANCH = auto()
    TAG = auto()


@dataclass
class GitResult:
    """Data class to hold the result of a Git operation."""

    success: bool
    output: str = ""
    error: Optional[str] = None
    data: Any = None


class GitInterface(ABC):
    """
    Abstract base class for Git operations.

    This class defines the interface that all Git implementations must follow.
    """

    def __init__(self, repo_path: Optional[Union[str, Path]] = None):
        """
        Initialize the GitInterface.

        Args:
            repo_path: Path to the Git repository (optional)
        """
        self.repo_path = Path(repo_path).resolve() if repo_path else None
        self._initialized = False

    @abstractmethod
    def initialize(
        self, repo_url: Optional[str] = None, clone_path: Optional[Union[str, Path]] = None
    ) -> 'GitInterface':
        """
        Initialize the Git repository.

        If repo_url is provided, clone the repository. Otherwise, initialize a new one.

        Args:
            repo_url: URL of the repository to clone (optional)
            clone_path: Path where to clone the repository (optional if repo_url is None)

        Returns:
            Self for method chaining
        """
        pass

    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if the Git repository is properly initialized."""
        pass

    @abstractmethod
    def clone(
        self, repo_url: str, target_path: Optional[Union[str, Path]] = None
    ) -> 'GitInterface':
        """
        Clone a Git repository.

        Args:
            repo_url: URL of the repository to clone
            target_path: Path where to clone the repository

        Returns:
            Self for method chaining
        """
        pass

    @abstractmethod
    def pull(self, remote: str = "origin", branch: str = "main") -> GitResult:
        """
        Pull changes from a remote repository.

        Args:
            remote: Name of the remote (default: 'origin')
            branch: Name of the branch to pull (default: 'main')

        Returns:
            GitResult with the operation result
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def commit(self, message: str, files: Optional[List[Union[str, Path]]] = None) -> GitResult:
        """
        Commit changes to the repository.

        Args:
            message: Commit message
            files: List of files to include in the commit (all if None)

        Returns:
            GitResult with the operation result
        """
        pass

    @abstractmethod
    def checkout(self, branch: str, create: bool = False) -> GitResult:
        """
        Checkout a branch.

        Args:
            branch: Name of the branch to checkout
            create: Whether to create the branch if it doesn't exist (default: False)

        Returns:
            GitResult with the operation result
        """
        pass

    @abstractmethod
    def status(self) -> GitResult:
        """
        Get the status of the repository.

        Returns:
            GitResult with status information
        """
        pass

    @abstractmethod
    def diff(self, staged: bool = False) -> GitResult:
        """
        Get the diff of the repository.

        Args:
            staged: Whether to show staged changes (default: False)

        Returns:
            GitResult with diff information
        """
        pass

    @abstractmethod
    def log(self, n: int = 10) -> GitResult:
        """
        Get the commit log.

        Args:
            n: Number of commits to show (default: 10)

        Returns:
            GitResult with log information
        """
        pass

    @abstractmethod
    def branch(self, name: Optional[str] = None, delete: bool = False) -> GitResult:
        """
        List, create, or delete branches.

        Args:
            name: Name of the branch to create or delete
            delete: Whether to delete the branch (default: False)

        Returns:
            GitResult with branch information
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_file_content(self, file_path: Union[str, Path]) -> Optional[str]:
        """
        Get the content of a file from the repository.

        Args:
            file_path: Path to the file (relative to repo root)

        Returns:
            File content as string, or None if file doesn't exist
        """
        pass

    @abstractmethod
    def write_file_content(self, file_path: Union[str, Path], content: str) -> bool:
        """
        Write content to a file in the repository.

        Args:
            file_path: Path to the file (relative to repo root)
            content: Content to write to the file

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_repository_structure(self) -> Dict[str, Any]:
        """
        Get the structure of the repository as a nested dictionary.

        Returns:
            Nested dictionary representing the repository structure
        """
        pass

    def _run_git_command(
        self, args: List[str], cwd: Optional[Union[str, Path]] = None
    ) -> Tuple[bool, str, str]:
        """
        Run a Git command and return the result.

        Args:
            args: List of command-line arguments
            cwd: Working directory for the command

        Returns:
            Tuple of (success, stdout, stderr)
        """
        cwd = Path(cwd) if cwd else self.repo_path
        if not cwd:
            raise ValueError("No repository path specified")

        try:
            result = subprocess.run(  # nosec
                ["git"] + args, cwd=str(cwd), capture_output=True, text=True, check=False
            )
            return (result.returncode == 0, result.stdout.strip(), result.stderr.strip())
        except Exception as e:
            logger.error(f"Error running Git command: {e}")
            return False, "", str(e)

    def __str__(self) -> str:
        """String representation of the GitInterface."""
        return f"{self.__class__.__name__}(repo_path={self.repo_path}, initialized={self._initialized})"
