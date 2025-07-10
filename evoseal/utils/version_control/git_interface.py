"""
GitInterface - Base class for Git operations in EVOSEAL

This module provides an abstract base class for Git operations with a consistent
interface that can be implemented by different backends.
"""

import logging
import os
import shutil
import subprocess  # nosec
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union, cast

from .exceptions import (
    AuthenticationError,
    BranchNotFoundError,
    GitCommandError,
    GitError,
    GitOperationError,
    HTTPSAuthenticationError,
    InvalidGitRepositoryError,
    MergeConflictError,
    PushRejectedError,
    RepositoryNotFoundError,
    SSHAuthenticationError,
)

# Type variable for the GitInterface class
TGitInterface = TypeVar('TGitInterface', bound='GitInterface')

# Type for progress callback functions
ProgressCallback = Callable[[str, int, int, int], None]

logger = logging.getLogger(__name__)

# Default timeout for Git operations (in seconds)
DEFAULT_GIT_TIMEOUT = 300  # 5 minutes


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

    def __init__(
        self,
        repo_path: Optional[Union[str, Path]] = None,
        ssh_key_path: Optional[Union[str, Path]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = DEFAULT_GIT_TIMEOUT,
    ):
        """
        Initialize the GitInterface.

        Args:
            repo_path: Path to the Git repository (optional)
            ssh_key_path: Path to SSH private key for authentication (optional)
            username: Username for authentication (optional)
            password: Password or personal access token for authentication (optional)
            timeout: Timeout for Git operations in seconds (default: 300)
        """
        self.repo_path = Path(repo_path).resolve() if repo_path else None
        self.ssh_key_path = Path(ssh_key_path) if ssh_key_path else None
        self.username = username
        self._password = password
        self.timeout = timeout
        self._initialized = False
        self._ssh_auth_sock = os.environ.get('SSH_AUTH_SOCK')

        # Validate SSH key if provided
        if self.ssh_key_path and not self.ssh_key_path.exists():
            raise ValueError(f"SSH key not found at {self.ssh_key_path}")

        # Set up environment for Git operations
        self._env = os.environ.copy()
        if self.ssh_key_path:
            self._env['GIT_SSH_COMMAND'] = f'ssh -i {self.ssh_key_path} -o IdentitiesOnly=yes'
        if self._password:
            # Configure Git to use the credential helper for this repo
            self._configure_credential_helper()

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

    def _configure_credential_helper(self) -> None:
        """Configure Git to use the credential helper for this repository."""
        if not self.repo_path:
            return

        # Configure Git to cache credentials in memory for a short time
        self._run_git_command(["config", "--local", "credential.helper", "cache"])
        self._run_git_command(["config", "--local", "credential.helper", "'cache --timeout=300'"])

    def _get_auth_env(self) -> Dict[str, str]:
        """Get the environment variables for authentication."""
        env = self._env.copy()

        # Set up SSH agent if available
        if self._ssh_auth_sock:
            env['SSH_AUTH_SOCK'] = self._ssh_auth_sock

        # Set up username and password for HTTPS
        if self.username and self._password:
            env['GIT_ASKPASS'] = 'true'
            env['GIT_TERMINAL_PROMPT'] = '0'

        return env

    def _run_git_command(
        self,
        args: List[str],
        cwd: Optional[Union[str, Path]] = None,
        input_data: Optional[str] = None,
        retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Tuple[bool, str, str]:
        """
        Run a Git command with enhanced error handling and retries.

        Args:
            args: List of command-line arguments
            cwd: Working directory for the command
            input_data: Input data to pass to the command (optional)
            retries: Number of retry attempts for transient failures
            retry_delay: Initial delay between retries in seconds (will be doubled on each retry)

        Returns:
            Tuple of (success, stdout, stderr)

        Raises:
            GitCommandError: If the command fails after all retries
        """
        cwd = Path(cwd) if cwd else self.repo_path
        if not cwd:
            raise ValueError("No repository path specified")

        last_error = None

        for attempt in range(retries):
            try:
                # Add authentication parameters if needed
                cmd = ["git"] + args

                # Run the command with subprocess.run() for better security and simplicity
                try:
                    # Using subprocess.run() with a list of arguments is safe (no shell injection)
                    result = subprocess.run(  # nosec: B603 - subprocess call with shell=False is safe here
                        cmd,
                        cwd=str(cwd),
                        input=input_data,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=self.timeout,
                        env=self._get_auth_env(),
                        check=False,  # We'll handle non-zero return codes ourselves
                    )
                    returncode = result.returncode
                    stdout = result.stdout
                    stderr = result.stderr
                except subprocess.TimeoutExpired as e:
                    raise GitCommandError(
                        f"Git command timed out after {self.timeout} seconds: {' '.join(cmd)}"
                    ) from e
                except Exception as e:
                    raise GitCommandError(f"Error executing Git command: {e}") from e

                # Check for authentication errors
                if "Permission denied" in stderr or "Authentication failed" in stderr:
                    if "publickey" in stderr.lower():
                        raise SSHAuthenticationError("SSH authentication failed")
                    else:
                        raise HTTPSAuthenticationError("HTTPS authentication failed")

                # Check for other common errors
                if "Repository not found" in stderr:
                    raise RepositoryNotFoundError(f"Repository not found: {stderr.strip()}")

                if "branch not found" in stderr.lower():
                    raise BranchNotFoundError(f"Branch not found: {stderr.strip()}")

                if "merge conflict" in stderr.lower():
                    raise MergeConflictError(f"Merge conflict: {stderr.strip()}")

                if "[rejected]" in stderr and "failed to push" in stderr.lower():
                    raise PushRejectedError(f"Push rejected: {stderr.strip()}")

                # If command was successful, return the result
                if returncode == 0:
                    return True, stdout.strip(), stderr.strip()

                # If we get here, there was an error but not one we specifically handle
                last_error = GitCommandError(
                    f"Git command failed with return code {returncode}",
                    " ".join(cmd),
                    returncode,
                    stdout,
                    stderr,
                )

                # If this is a retryable error and we have retries left, wait and try again
                if attempt < retries - 1 and self._is_retryable_error(stderr):
                    time.sleep(retry_delay * (2**attempt))  # Exponential backoff
                    continue

                # Otherwise, raise the error
                raise last_error

            except Exception as e:
                if attempt == retries - 1:  # Last attempt
                    logger.error(
                        f"Error running Git command (attempt {attempt + 1}/{retries}): {e}"
                    )
                    if isinstance(e, GitError):
                        raise
                    raise GitCommandError(str(e), " ".join(cmd), -1, "", str(e)) from e

                # Wait before retrying
                time.sleep(retry_delay * (2**attempt))

        # This should never be reached, but just in case
        raise GitCommandError(
            "Unexpected error in _run_git_command", " ".join(cmd), -1, "", "Unknown error"
        )

    def _is_retryable_error(self, stderr: str) -> bool:
        """Check if an error is retryable based on the error message."""
        retryable_errors = [
            "connection timed out",
            "could not read from remote repository",
            "early eof",
            "the remote end hung up unexpectedly",
            "request timed out",
            "operation timed out",
            "failed to connect to",
            "connection reset by peer",
            "packet write with broken header",
            "packet write wait",
        ]

        return any(error in stderr.lower() for error in retryable_errors)

    def __str__(self) -> str:
        """String representation of the GitInterface."""
        return f"{self.__class__.__name__}(repo_path={self.repo_path}, initialized={self._initialized})"
