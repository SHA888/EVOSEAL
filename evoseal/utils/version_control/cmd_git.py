"""
Command-line Git implementation for GitInterface.

This module provides an implementation of GitInterface using the git command-line tool.
"""

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

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
from .git_interface import GitInterface, GitOperation, GitResult, ProgressCallback

logger = logging.getLogger(__name__)


class CmdGit(GitInterface):
    """
    Implementation of GitInterface using the git command-line tool.

    This implementation provides a robust wrapper around the Git command-line interface
    with support for authentication, error handling, and progress reporting.
    """

    def __init__(
        self,
        repo_path: Optional[Union[str, Path]] = None,
        ssh_key_path: Optional[Union[str, Path]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 300,  # 5 minutes default timeout
    ):
        """
        Initialize the CmdGit instance.

        Args:
            repo_path: Path to the Git repository (optional)
            ssh_key_path: Path to SSH private key for authentication (optional)
            username: Username for authentication (optional)
            password: Password or personal access token for authentication (optional)
            timeout: Timeout for Git operations in seconds (default: 300)
        """
        super().__init__(
            repo_path=repo_path,
            ssh_key_path=ssh_key_path,
            username=username,
            password=password,
            timeout=timeout,
        )

        # Only check if the repository is initialized if a path is provided
        # but don't require it to be initialized yet
        if repo_path:
            git_dir = Path(repo_path) / '.git'
            if git_dir.exists() or (Path(repo_path) / 'HEAD').exists():
                self._initialized = True

        # Store progress callback
        self._progress_callback = None

    def initialize(
        self,
        repo_url: Optional[str] = None,
        clone_path: Optional[Union[str, Path]] = None,
        bare: bool = False,
        initial_branch: Optional[str] = None,
    ) -> 'CmdGit':
        """
        Initialize the Git repository.

        If repo_url is provided, clone the repository. Otherwise, initialize a new one.

        Args:
            repo_url: URL of the repository to clone (optional)
            clone_path: Path where to clone the repository (required if repo_url is provided)
            bare: Whether to create a bare repository (default: False)
            initial_branch: Name of the initial branch (default: 'main' or Git's default)

        Returns:
            Self for method chaining

        Raises:
            ValueError: If required parameters are missing
            GitError: If repository initialization fails
        """
        try:
            if repo_url:
                if not clone_path:
                    raise ValueError("clone_path is required when repo_url is provided")
                return self.clone(repo_url, clone_path)

            if not self.repo_path:
                raise ValueError("repo_path must be set when initializing a new repository")

            # Check if repository already exists
            git_dir = self.repo_path / ".git"
            if git_dir.exists() or (self.repo_path / "HEAD").exists():
                self._initialized = True
                logger.info(f"Using existing Git repository at {self.repo_path}")
                return self

            # Initialize new repository
            cmd = ["init"]
            if bare:
                cmd.append("--bare")
            if initial_branch:
                cmd.extend(["-b", initial_branch])

            success, stdout, stderr = self._run_git_command(cmd)
            if not success:
                raise GitError(f"Failed to initialize Git repository: {stderr}")

            logger.info(f"Initialized new Git repository at {self.repo_path}")
            self._initialized = True
            return self

        except Exception as e:
            logger.error(f"Failed to initialize Git repository: {e}")
            if isinstance(e, (ValueError, GitError)):
                raise
            raise GitError(f"Failed to initialize Git repository: {e}") from e

    def is_initialized(self) -> bool:
        """Check if the Git repository is properly initialized."""
        if not self.repo_path:
            return False
        return (self.repo_path / ".git").exists()

    def clone(
        self,
        repo_url: str,
        target_path: Optional[Union[str, Path]] = None,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> 'CmdGit':
        """
        Clone a Git repository with enhanced options and progress reporting.

        Args:
            repo_url: URL of the repository to clone
            target_path: Path where to clone the repository
            branch: Branch to checkout after clone (optional)
            depth: Create a shallow clone with history truncated to the specified
                  number of commits (optional)
            progress_callback: Callback function for progress updates

        Returns:
            Self for method chaining

        Raises:
            GitError: If the clone operation fails
            RepositoryNotFoundError: If the repository doesn't exist
            AuthenticationError: If authentication fails
        """
        try:
            # Set up progress callback
            self._progress_callback = progress_callback

            # Determine target path
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

            # Build clone command
            cmd = ["clone"]

            # Add progress flag if callback is provided
            if progress_callback is not None:
                cmd.append("--progress")

            # Add depth if specified
            if depth is not None:
                cmd.extend(["--depth", str(depth)])

            # Add branch if specified
            if branch:
                cmd.extend(["-b", branch])

            # Add repository URL and target path
            cmd.extend([repo_url, str(target_path)])

            # Run the clone command
            success, stdout, stderr = self._run_git_command(
                cmd,
                cwd=target_path.parent,
            )

            if not success:
                if "Repository not found" in stderr:
                    raise RepositoryNotFoundError(f"Repository not found: {repo_url}")
                if any(msg in stderr for msg in ["Permission denied", "Authentication failed"]):
                    if "publickey" in stderr.lower():
                        raise SSHAuthenticationError("SSH authentication failed")
                    else:
                        raise HTTPSAuthenticationError("HTTPS authentication failed")
                raise GitError(f"Failed to clone repository: {stderr}")

            logger.info(f"Successfully cloned {repo_url} to {target_path}")
            self.repo_path = target_path
            self._initialized = True
            return self

        except Exception as e:
            logger.error(f"Failed to clone repository {repo_url}: {e}")
            if isinstance(e, (RepositoryNotFoundError, AuthenticationError, GitError)):
                raise
            raise GitError(f"Failed to clone repository: {e}") from e

        finally:
            # Reset progress callback
            self._progress_callback = None

    def pull(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        rebase: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GitResult:
        """
        Pull changes from a remote repository with enhanced options.

        Args:
            remote: Name of the remote (default: 'origin')
            branch: Name of the branch to pull (default: current branch)
            rebase: Whether to use rebase instead of merge (default: False)
            progress_callback: Callback function for progress updates

        Returns:
            GitResult with the operation result

        Raises:
            GitError: If the pull operation fails
            MergeConflictError: If there are merge conflicts
        """
        try:
            self._check_initialized()
            self._progress_callback = progress_callback

            cmd = ["pull"]

            # Add progress flag if callback is provided
            if progress_callback is not None:
                cmd.append("--progress")

            # Add rebase flag if requested
            if rebase:
                cmd.append("--rebase")

            # Add remote and branch
            cmd.append(remote)
            if branch:
                cmd.append(branch)

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                if "CONFLICT" in stderr or "merge conflict" in stderr.lower():
                    raise MergeConflictError("Merge conflicts detected during pull")
                if any(msg in stderr for msg in ["Permission denied", "Authentication failed"]):
                    if "publickey" in stderr.lower():
                        raise SSHAuthenticationError("SSH authentication failed")
                    else:
                        raise HTTPSAuthenticationError("HTTPS authentication failed")
                raise GitError(f"Failed to pull changes: {stderr}")

            logger.info(
                f"Successfully pulled changes from {remote}/{branch if branch else 'current branch'}"
            )
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to pull changes: {e}")
            if isinstance(e, (MergeConflictError, AuthenticationError, GitError)):
                raise
            raise GitError(f"Failed to pull changes: {e}") from e

        finally:
            self._progress_callback = None

    def push(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        force: bool = False,
        set_upstream: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GitResult:
        """
        Push changes to a remote repository with enhanced options.

        Args:
            remote: Name of the remote (default: 'origin')
            branch: Name of the branch to push (default: current branch)
            force: Whether to force push (default: False)
            set_upstream: Whether to set the upstream branch (default: False)
            progress_callback: Callback function for progress updates

        Returns:
            GitResult with the operation result

        Raises:
            GitError: If the push operation fails
            PushRejectedError: If the push is rejected by the remote
        """
        try:
            self._check_initialized()
            self._progress_callback = progress_callback

            cmd = ["push"]

            # Add progress flag if callback is provided
            if progress_callback is not None:
                cmd.append("--progress")

            # Add force flag if requested
            if force:
                cmd.append("--force")

            # Set upstream if requested
            if set_upstream:
                cmd.append("--set-upstream")

            # Add remote and branch
            cmd.append(remote)
            if branch:
                cmd.append(branch)

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                if "rejected" in stderr.lower() and "failed to push" in stderr.lower():
                    raise PushRejectedError(f"Push was rejected: {stderr.strip()}")
                if any(msg in stderr for msg in ["Permission denied", "Authentication failed"]):
                    if "publickey" in stderr.lower():
                        raise SSHAuthenticationError("SSH authentication failed")
                    else:
                        raise HTTPSAuthenticationError("HTTPS authentication failed")
                raise GitError(f"Failed to push changes: {stderr}")

            logger.info(
                f"Successfully pushed changes to {remote}/{branch if branch else 'current branch'}"
            )
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to push changes: {e}")
            if isinstance(e, (PushRejectedError, AuthenticationError, GitError)):
                raise
            raise GitError(f"Failed to push changes: {e}") from e

        finally:
            self._progress_callback = None

    def commit(
        self,
        message: str,
        files: Optional[List[Union[str, Path]]] = None,
        allow_empty: bool = False,
        amend: bool = False,
        no_verify: bool = False,
    ) -> GitResult:
        """
        Commit changes to the repository with enhanced options.

        Args:
            message: Commit message
            files: List of files to include in the commit (all if None)
            allow_empty: Allow an empty commit (default: False)
            amend: Amend the previous commit (default: False)
            no_verify: Bypass pre-commit and commit-msg hooks (default: False)

        Returns:
            GitResult with the operation result

        Raises:
            GitError: If the commit operation fails
        """
        try:
            self._check_initialized()

            # Stage files if specified
            if files:
                file_paths = [str(f) for f in files]
                success, stdout, stderr = self._run_git_command(["add"] + file_paths)
                if not success:
                    raise GitError(f"Failed to stage files: {stderr}")
            else:
                # Stage all changes
                success, stdout, stderr = self._run_git_command(["add", "."])
                if not success:
                    raise GitError(f"Failed to stage changes: {stderr}")

            # Build commit command
            cmd = ["commit", "-m", message]

            # Add flags based on options
            if allow_empty:
                cmd.append("--allow-empty")
            if amend:
                cmd.append("--amend")
            if no_verify:
                cmd.append("--no-verify")

            # Create commit
            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                if "nothing to commit" in stderr.lower():
                    logger.info("No changes to commit")
                    return GitResult(True, "No changes to commit", None)
                raise GitError(f"Failed to create commit: {stderr}")

            logger.info(f"Created commit: {message}")
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to create commit: {e}")
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to create commit: {e}") from e

    def checkout(
        self,
        branch: str,
        create: bool = False,
        start_point: Optional[str] = None,
        force: bool = False,
    ) -> GitResult:
        """
        Checkout a branch or commit with enhanced options.

        Args:
            branch: Name of the branch or commit to checkout
            create: Whether to create the branch if it doesn't exist (default: False)
            start_point: The commit to start the new branch from (only used if create=True)
            force: Discard local changes if needed (default: False)

        Returns:
            GitResult with the operation result

        Raises:
            GitError: If the checkout operation fails
            BranchNotFoundError: If the branch doesn't exist and create=False
        """
        try:
            self._check_initialized()

            cmd = ["checkout"]

            # Add force flag if requested
            if force:
                cmd.append("--force")

            # Handle branch creation if requested
            if create:
                cmd.append("-b")
                cmd.append(branch)
                if start_point:
                    cmd.append(start_point)
            else:
                cmd.append(branch)

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                if "did not match any file(s) known to git" in stderr:
                    raise BranchNotFoundError(f"Branch or commit not found: {branch}")
                if "Your local changes" in stderr and not force:
                    raise GitError(
                        "Local changes would be overwritten by checkout. "
                        "Use force=True to discard local changes."
                    )
                raise GitError(f"Failed to checkout {branch}: {stderr}")

            action = "Created and checked out" if create else "Checked out"
            logger.info(f"{action} branch: {branch}")
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to checkout {branch}: {e}")
            if isinstance(e, (BranchNotFoundError, GitError)):
                raise
            raise GitError(f"Failed to checkout {branch}: {e}") from e

    def status(self, short: bool = False, branch: bool = False) -> GitResult:
        """
        Get the status of the repository with enhanced options.

        Args:
            short: Give the output in the short-format (default: False)
            branch: Show the branch and tracking info even in short-format (default: False)

        Returns:
            GitResult with status information

        Raises:
            GitError: If the status command fails
        """
        try:
            self._check_initialized()

            cmd = ["status"]

            # Add flags based on options
            if short:
                cmd.append("--short")
                if branch:
                    cmd.append("--branch")

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                raise GitError(f"Failed to get repository status: {stderr}")

            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to get repository status: {e}")
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to get repository status: {e}") from e

    def diff(
        self,
        staged: bool = False,
        cached: bool = False,
        name_only: bool = False,
        color: bool = True,
        **kwargs,
    ) -> GitResult:
        """
        Get the diff of the repository with enhanced options.

        Args:
            staged: Show staged changes (same as --cached)
            cached: Show staged changes (same as --staged)
            name_only: Show only names of changed files
            color: Whether to use color in the output
            **kwargs: Additional diff options as keyword arguments
                     (e.g., ignore_space_change=True becomes --ignore-space-change)

        Returns:
            GitResult with diff information

        Raises:
            GitError: If the diff command fails
        """
        try:
            self._check_initialized()

            cmd = ["diff"]

            # Add flags based on options
            if staged or cached:
                cmd.append("--cached")
            if name_only:
                cmd.append("--name-only")
            if not color:
                cmd.append("--no-color")

            # Add additional options from kwargs
            for key, value in kwargs.items():
                if value is True:
                    # Convert snake_case to kebab-case
                    flag = "--" + key.replace("_", "-")
                    cmd.append(flag)

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                raise GitError(f"Failed to get diff: {stderr}")

            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to get diff: {e}")
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to get diff: {e}") from e

    def log(
        self,
        n: Optional[int] = None,
        max_count: Optional[int] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        author: Optional[str] = None,
        grep: Optional[str] = None,
        oneline: bool = True,
        **kwargs,
    ) -> GitResult:
        """
        Get the commit log with enhanced filtering and formatting options.

        Args:
            n: Number of commits to show (shorthand for --max-count)
            max_count: Maximum number of commits to show
            since: Show commits more recent than a specific date
            until: Show commits older than a specific date
            author: Filter commits by author
            grep: Filter commits whose message matches the given pattern
            oneline: Show each commit on a single line (default: True)
            **kwargs: Additional log options as keyword arguments

        Returns:
            GitResult with log information

        Raises:
            GitError: If the log command fails
        """
        try:
            self._check_initialized()

            cmd = ["log"]

            # Add flags based on options
            if n is not None:
                cmd.extend(["-n", str(n)])
            if max_count is not None:
                cmd.extend(["--max-count", str(max_count)])
            if since:
                cmd.extend(["--since", since])
            if until:
                cmd.extend(["--until", until])
            if author:
                cmd.extend(["--author", author])
            if grep:
                cmd.extend(["--grep", grep])
            if oneline:
                cmd.append("--oneline")

            # Add additional options from kwargs
            for key, value in kwargs.items():
                if value is True:
                    # Convert snake_case to kebab-case
                    flag = "--" + key.replace("_", "-")
                    cmd.append(flag)
                elif value is not None and value is not False:
                    flag = "--" + key.replace("_", "-")
                    cmd.extend([flag, str(value)])

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                raise GitError(f"Failed to get commit log: {stderr}")

            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to get commit log: {e}")
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to get commit log: {e}") from e

    def branch(
        self,
        name: Optional[str] = None,
        delete: bool = False,
        force: bool = False,
        track: Optional[str] = None,
        set_upstream_to: Optional[str] = None,
    ) -> GitResult:
        """
        List, create, or delete branches with enhanced options.

        Args:
            name: Name of the branch to create or delete
            delete: Whether to delete the branch (default: False)
            force: Force the operation (e.g., delete unmerged branch)
            track: Set up tracking information (for new branches)
            set_upstream_to: Set up tracking information for an existing branch

        Returns:
            GitResult with branch information

        Raises:
            GitError: If the branch operation fails
            BranchNotFoundError: If the branch doesn't exist when trying to delete
        """
        try:
            self._check_initialized()

            if name is None:
                # List branches
                success, stdout, stderr = self._run_git_command(["branch", "--list"])
                if not success:
                    raise GitError(f"Failed to list branches: {stderr}")
                return GitResult(True, stdout, None)

            cmd = ["branch"]

            if delete:
                # Delete branch
                cmd.append("-D" if force else "-d")
                cmd.append(name)
            elif set_upstream_to:
                # Set upstream for existing branch
                cmd.extend(["--set-upstream-to", set_upstream_to, name])
                name = None  # Don't add name again
            else:
                # Create branch
                if force:
                    cmd.append("-f")
                if track:
                    cmd.extend(["--track", track])

            if name:
                cmd.append(name)

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                if "not found" in stderr.lower():
                    raise BranchNotFoundError(f"Branch not found: {name}")
                raise GitError(f"Branch operation failed: {stderr}")

            action = "Deleted" if delete else "Created" if name else "Updated"
            logger.info(f"{action} branch: {name}")
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to perform branch operation: {e}")
            if isinstance(e, (BranchNotFoundError, GitError)):
                raise
            raise GitError(f"Failed to perform branch operation: {e}") from e

    def list_remotes(self, verbose: bool = False) -> Dict[str, str]:
        """
        List all remotes for the repository.

        Args:
            verbose: Whether to include remote URLs (default: False)

        Returns:
            Dictionary of remote names to URLs (if verbose) or empty dict (if not verbose)

        Raises:
            GitError: If the remote listing fails
        """
        try:
            self._check_initialized()

            cmd = ["remote", "-v"] if verbose else ["remote"]
            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                raise GitError(f"Failed to list remotes: {stderr}")

            if not verbose:
                return {name: "" for name in stdout.splitlines() if name.strip()}

            # Parse verbose output: name<tab>url (type)
            remotes = {}
            for line in stdout.splitlines():
                if "\t" in line and " " in line:
                    name, rest = line.split("\t", 1)
                    url = rest.split(" ", 1)[0]
                    remotes[name] = url

            return remotes

        except Exception as e:
            logger.error(f"Failed to list remotes: {e}")
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to list remotes: {e}") from e

    def add_remote(
        self,
        name: str,
        url: str,
        fetch: bool = True,
        force: bool = False,
    ) -> GitResult:
        """
        Add a new remote to the repository.

        Args:
            name: Name of the remote to add
            url: URL of the remote repository
            fetch: Whether to run git fetch after adding the remote
            force: If True, allows overwriting an existing remote

        Returns:
            GitResult with the operation result

        Raises:
            GitError: If the remote addition fails
            ValueError: If the remote already exists and force=False
        """
        try:
            self._check_initialized()

            # Check if remote already exists
            remotes = self.list_remotes()
            if name in remotes:
                if not force:
                    raise ValueError(
                        f"Remote '{name}' already exists. Use force=True to overwrite."
                    )
                # Remove existing remote first
                self.remove_remote(name)

            cmd = ["remote", "add"]
            if not fetch:
                cmd.append("--no-fetch")
            cmd.extend([name, url])

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                raise GitError(f"Failed to add remote: {stderr}")

            logger.info(f"Added remote: {name} -> {url}")
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to add remote {name}: {e}")
            if isinstance(e, (ValueError, GitError)):
                raise
            raise GitError(f"Failed to add remote: {e}") from e

    def remove_remote(self, name: str) -> GitResult:
        """
        Remove a remote from the repository.

        Args:
            name: Name of the remote to remove

        Returns:
            GitResult with the operation result

        Raises:
            GitError: If the remote removal fails
            ValueError: If the remote doesn't exist
        """
        try:
            self._check_initialized()

            # Check if remote exists
            remotes = self.list_remotes()
            if name not in remotes:
                raise ValueError(f"Remote '{name}' does not exist")

            success, stdout, stderr = self._run_git_command(["remote", "remove", name])

            if not success:
                raise GitError(f"Failed to remove remote: {stderr}")

            logger.info(f"Removed remote: {name}")
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to remove remote {name}: {e}")
            if isinstance(e, (ValueError, GitError)):
                raise
            raise GitError(f"Failed to remove remote: {e}") from e

    def set_remote_url(self, name: str, url: str, push: bool = False) -> GitResult:
        """
        Set the URL for a remote.

        Args:
            name: Name of the remote
            url: New URL for the remote
            push: Whether to set the push URL instead of the fetch URL

        Returns:
            GitResult with the operation result

        Raises:
            GitError: If the operation fails
            ValueError: If the remote doesn't exist
        """
        try:
            self._check_initialized()

            # Check if remote exists
            remotes = self.list_remotes()
            if name not in remotes:
                raise ValueError(f"Remote '{name}' does not exist")

            cmd = ["remote", "set-url"]
            if push:
                cmd.append("--push")
            cmd.extend([name, url])

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                raise GitError(f"Failed to set remote URL: {stderr}")

            action = "push URL" if push else "URL"
            logger.info(f"Set {action} for remote {name} to {url}")
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to set URL for remote {name}: {e}")
            if isinstance(e, (ValueError, GitError)):
                raise
            raise GitError(f"Failed to set remote URL: {e}") from e

    def tag(
        self,
        name: Optional[str] = None,
        message: Optional[str] = None,
        delete: bool = False,
        force: bool = False,
        sign: bool = False,
        sign_key: Optional[str] = None,
        commit: Optional[str] = None,
    ) -> GitResult:
        """
        List, create, or delete tags with enhanced options.

        Args:
            name: Name of the tag to create or delete
            message: Optional message for annotated tag
            delete: Whether to delete the tag (default: False)
            force: Force the operation (overwrite existing tag)
            sign: Create a signed tag (uses default GPG key)
            sign_key: Specific GPG key to sign with
            commit: Create tag at specific commit instead of HEAD

        Returns:
            GitResult with tag information

        Raises:
            GitError: If the tag operation fails
            ValueError: If required parameters are missing
        """
        try:
            self._check_initialized()

            if name is None:
                # List tags
                success, stdout, stderr = self._run_git_command(["tag", "--list"])
                if not success:
                    raise GitError(f"Failed to list tags: {stderr}")
                return GitResult(True, stdout, None)

            cmd = ["tag"]

            if delete:
                # Delete tag
                cmd.append("-d")
                if force:
                    cmd[1] = "-D"  # Replace -d with -D
                cmd.append(name)
            else:
                # Create tag
                if message:
                    cmd.extend(["-a", "-m", message])
                if force:
                    cmd.append("-f")
                if sign or sign_key:
                    cmd.append("-s" if not sign_key else f"-u {sign_key}")
                cmd.append(name)
                if commit:
                    cmd.append(commit)

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                if "already exists" in stderr and not force:
                    raise GitError(f"Tag '{name}' already exists. Use force=True to overwrite.")
                raise GitError(f"Tag operation failed: {stderr}")

            action = "Deleted" if delete else "Created"
            logger.info(f"{action} tag: {name}")
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to perform tag operation: {e}")
            if isinstance(e, (ValueError, GitError)):
                raise
            raise GitError(f"Failed to perform tag operation: {e}") from e

    def stash(
        self,
        action: str = "save",
        message: Optional[str] = None,
        include_untracked: bool = False,
        keep_index: bool = False,
        stash_id: Optional[Union[int, str]] = None,
        **kwargs,
    ) -> GitResult:
        """
        Stash changes in the working directory.

        Args:
            action: Stash action to perform. One of:
                   - 'save' (default): Save current changes to a new stash
                   - 'list': List all stashes
                   - 'show': Show the changes in a stash
                   - 'apply': Apply a stash without removing it
                   - 'pop': Apply and remove a stash
                   - 'drop': Remove a stash
                   - 'clear': Remove all stashes
            message: Optional message for the stash (used with 'save' action)
            include_untracked: Include untracked files in the stash
            keep_index: Keep changes staged in the index
            stash_id: ID of the stash to operate on (for show/apply/pop/drop)
            **kwargs: Additional options for specific actions

        Returns:
            GitResult with the operation result

        Raises:
            GitError: If the stash operation fails
            ValueError: If invalid parameters are provided
        """
        try:
            self._check_initialized()

            valid_actions = ["save", "list", "show", "apply", "pop", "drop", "clear"]
            if action not in valid_actions:
                raise ValueError(
                    f"Invalid stash action. Must be one of: {', '.join(valid_actions)}"
                )

            cmd = ["stash"]

            if action == "save":
                if message:
                    cmd.extend(["save", "-m", message])
                else:
                    cmd.append("save")
                if include_untracked:
                    cmd.append("--include-untracked")
                if keep_index:
                    cmd.append("--keep-index")

            elif action == "list":
                cmd.append("list")
                if kwargs.get("stat"):
                    cmd.append("--stat")
                if kwargs.get("patch"):
                    cmd.append("-p")

            elif action in ["show", "apply", "pop", "drop"]:
                if stash_id is None and action != "show":
                    raise ValueError(f"stash_id is required for '{action}' action")
                cmd.append(action)
                if stash_id is not None:
                    cmd.append(f"stash@{{{stash_id}}}" if isinstance(stash_id, int) else stash_id)
                if action == "show" and kwargs.get("stat"):
                    cmd.append("--stat")

            elif action == "clear":
                cmd.append("clear")

            success, stdout, stderr = self._run_git_command(cmd)

            if not success:
                if "No stash found" in stderr:
                    return GitResult(True, "No stashes found", None)
                if "No local changes to save" in stderr:
                    return GitResult(True, "No local changes to stash", None)
                raise GitError(f"Stash operation failed: {stderr}")

            logger.info(f"Successfully performed stash {action}")
            return GitResult(True, stdout, None)

        except Exception as e:
            logger.error(f"Failed to perform stash {action}: {e}")
            if isinstance(e, (ValueError, GitError)):
                raise
            raise GitError(f"Failed to perform stash operation: {e}") from e

    def get_file_content(
        self,
        file_path: Union[str, Path],
        ref: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Optional[str]:
        """
        Get the content of a file in the repository.

        Args:
            file_path: Path to the file (relative to repo root)
            ref: Git reference (commit hash, branch, or tag) to get the file from.
                 If None, gets the file from the working directory.
            encoding: Text encoding to use (default: 'utf-8')

        Returns:
            Content of the file as a string, or None if the file doesn't exist

        Raises:
            GitError: If there's an error accessing the file
            FileNotFoundError: If the file doesn't exist in the specified reference
        """
        try:
            self._check_initialized()
            file_path = Path(file_path)

            if ref is not None:
                # Get file content from git object database
                cmd = ["show", f"{ref}:{file_path}"]
                success, stdout, stderr = self._run_git_command(cmd)

                if not success:
                    if "exists on disk, but not in" in stderr:
                        raise FileNotFoundError(
                            f"File '{file_path}' not found in reference '{ref}'"
                        )
                    raise GitError(f"Failed to get file content: {stderr}")

                return stdout

            # Get file content from working directory
            full_path = self.repo_path / file_path
            try:
                return full_path.read_text(encoding=encoding)
            except UnicodeDecodeError as e:
                raise GitError(
                    f"Failed to decode file '{file_path}' with encoding {encoding}"
                ) from e

        except FileNotFoundError as e:
            logger.debug(f"File not found: {file_path}")
            return None

        except Exception as e:
            logger.error(f"Error getting file content for {file_path}: {e}")
            if isinstance(e, (FileNotFoundError, GitError)):
                raise
            raise GitError(f"Failed to get file content: {e}") from e

    def write_file_content(
        self,
        file_path: Union[str, Path],
        content: str,
        encoding: str = "utf-8",
        create_parents: bool = True,
        mode: Optional[int] = None,
    ) -> bool:
        """
        Write content to a file in the repository.

        Args:
            file_path: Path to the file (relative to repo root)
            content: Content to write to the file
            encoding: Text encoding to use (default: 'utf-8')
            create_parents: Whether to create parent directories if they don't exist
            mode: File mode (permissions) to set (e.g., 0o644 for rw-r--r--)

        Returns:
            True if successful, False otherwise

        Raises:
            GitError: If there's an error writing the file
        """
        try:
            self._check_initialized()
            file_path = Path(file_path)
            full_path = self.repo_path / file_path

            # Create parent directories if needed
            if create_parents:
                full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file content
            try:
                full_path.write_text(content, encoding=encoding)
            except UnicodeEncodeError as e:
                raise GitError(f"Failed to encode content with encoding {encoding}: {e}") from e

            # Set file mode if specified
            if mode is not None:
                try:
                    full_path.chmod(mode)
                except Exception as e:
                    logger.warning(f"Failed to set file mode for {file_path}: {e}")

            logger.debug(f"Successfully wrote to {file_path}")
            return True

        except PermissionError as e:
            error_msg = f"Permission denied when writing to {file_path}"
            logger.error(error_msg)
            raise GitError(error_msg) from e

        except Exception as e:
            logger.error(f"Error getting repository structure: {e}")
            if isinstance(e, (ValueError, GitError)):
                raise
            raise GitError(f"Failed to get repository structure: {e}") from e

    def get_repository_structure(
        self,
        ref: Optional[str] = None,
        path: Optional[Union[str, Path]] = None,
        recursive: bool = True,
        include_hidden: bool = False,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get the structure of the repository with detailed information.

        Args:
            ref: Git reference (commit hash, branch, or tag) to get the structure from.
                 If None, gets the structure from the working directory.
            path: Subdirectory path to get structure for (relative to repo root).
                 If None, gets structure for the entire repository.
            recursive: Whether to include subdirectories recursively.
            include_hidden: Whether to include hidden files/directories (starting with .).
            max_depth: Maximum depth to traverse (None for unlimited).

        Returns:
            Dictionary representing the repository structure with metadata.

        Raises:
            GitError: If there's an error getting the repository structure.
            ValueError: If the specified path doesn't exist.
        """
        try:
            self._check_initialized()

            base_path = self.repo_path
            if path is not None:
                path = Path(path)
                if not path.is_absolute():
                    path = self.repo_path / path
                if not path.exists():
                    raise ValueError(f"Path not found: {path}")
                base_path = path

            def get_structure(current_path: Path, current_depth: int = 0) -> Dict[str, Any]:
                """Recursively build the repository structure."""
                logger.debug(
                    f"Processing path: {current_path}, depth: {current_depth}, recursive: {recursive}"
                )

                if not current_path.exists():
                    logger.debug(f"Path does not exist: {current_path}")
                    return {}

                # Skip .git directory unless explicitly included
                if ".git" in current_path.parts and not include_hidden:
                    logger.debug(f"Skipping .git directory: {current_path}")
                    return {}

                # Skip hidden files/directories if not included
                if (
                    current_path.name.startswith('.')
                    and not include_hidden
                    and current_path != base_path
                ):
                    logger.debug(f"Skipping hidden path: {current_path}")
                    return {}

                # Check max depth
                if max_depth is not None and current_depth > max_depth:
                    logger.debug(f"Max depth reached at {current_path}")
                    return {
                        "type": "directory",
                        "path": str(current_path.relative_to(self.repo_path)),
                        "contents": {},
                        "truncated": True,
                    }

                if current_path.is_file():
                    stat = current_path.stat()
                    file_info = {
                        "type": "file",
                        "path": str(current_path.relative_to(self.repo_path)),
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "mode": oct(stat.st_mode)[-3:],
                    }
                    logger.debug(f"File found: {file_info}")
                    return file_info

                rel_path = str(current_path.relative_to(self.repo_path))
                structure = {
                    "type": "directory",
                    "path": rel_path,
                    "contents": {},
                }
                logger.debug(f"Processing directory: {rel_path}")

                try:
                    for item in current_path.iterdir():
                        if item.name == ".git" and not include_hidden:
                            logger.debug(f"Skipping .git directory: {item}")
                            continue
                        if item.name.startswith('.') and not include_hidden:
                            logger.debug(f"Skipping hidden item: {item}")
                            continue

                        logger.debug(f"Processing item: {item}")

                        if item.is_file():
                            # Always include files at the current level
                            stat = item.stat()
                            structure["contents"][item.name] = {
                                "type": "file",
                                "path": str(item.relative_to(self.repo_path)),
                                "size": stat.st_size,
                                "modified": stat.st_mtime,
                                "mode": oct(stat.st_mode)[-3:],
                            }
                            logger.debug(f"Added file to structure: {item.name}")
                        elif item.is_dir():
                            # For directories, include them but only process contents if recursive=True
                            dir_structure = {
                                "type": "directory",
                                "path": str(item.relative_to(self.repo_path)),
                                "contents": {},
                            }

                            if recursive:
                                # Only process directory contents if recursive is True
                                item_structure = get_structure(item, current_depth + 1)
                                if item_structure and "contents" in item_structure:
                                    dir_structure["contents"] = item_structure["contents"]

                            structure["contents"][item.name] = dir_structure
                            logger.debug(f"Added directory to structure: {item.name}")

                except PermissionError as e:
                    logger.warning(f"Permission denied reading directory {current_path}: {e}")
                    structure["error"] = "permission_denied"

                return structure

            # Get structure from git tree if ref is specified
            if ref is not None:
                try:
                    # Get the tree structure using git ls-tree
                    rel_path = "" if path is None else str(Path(path).relative_to(self.repo_path))
                    cmd = ["ls-tree", "-l", ref, rel_path] if rel_path else ["ls-tree", "-l", ref]
                    success, stdout, stderr = self._run_git_command(cmd)

                    if not success:
                        raise GitError(f"Failed to get repository structure: {stderr}")

                    # Parse the ls-tree output
                    structure = {
                        "type": "directory",
                        "path": "." if not rel_path else rel_path,
                        "ref": ref,
                        "contents": {},
                    }

                    for line in stdout.splitlines():
                        if not line.strip():
                            continue

                        # Format: <mode> <type> <sha> <size>\t<path>
                        parts = line.split('\t')
                        if len(parts) != 2:
                            continue

                        meta, item_path = parts
                        meta_parts = meta.split()
                        if len(meta_parts) < 3:
                            continue

                        item_name = Path(item_path).name
                        item_type = meta_parts[1]
                        item_mode = meta_parts[0]
                        item_sha = meta_parts[2]
                        item_size = int(meta_parts[3]) if len(meta_parts) > 3 else 0

                        if item_type == "blob":
                            structure["contents"][item_name] = {
                                "type": "file",
                                "path": item_path,
                                "sha": item_sha,
                                "size": item_size,
                                "mode": item_mode,
                            }
                        elif item_type == "tree" and recursive:
                            # For subdirectories, include basic info
                            structure["contents"][item_name] = {
                                "type": "directory",
                                "path": item_path,
                                "sha": item_sha,
                                "mode": item_mode,
                                "contents": {},
                            }

                    return structure

                except Exception as e:
                    logger.error(f"Error getting git tree structure: {e}")
                    raise GitError(f"Failed to get git tree structure: {e}") from e

            # Get structure from working directory
            structure = get_structure(base_path)
            logger.debug(f"Final structure: {structure}")
            return structure

        except Exception as e:
            logger.error(f"Error getting repository structure: {e}")
            if isinstance(e, (ValueError, GitError)):
                raise
            raise GitError(f"Failed to get repository structure: {e}") from e

    def get_file_history(
        self,
        file_path: Union[str, Path],
        limit: int = 10,
        ref: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get the commit history for a specific file.

        Args:
            file_path: Path to the file (relative to repo root)
            limit: Maximum number of commits to return (default: 10)
            ref: Git reference (commit hash, branch, or tag) to start from

        Returns:
            List of dictionaries containing commit information

        Raises:
            GitError: If there's an error getting the file history
            FileNotFoundError: If the file doesn't exist
        """
        try:
            self._check_initialized()
            file_path = Path(file_path)
            
            # Check if file exists in the specified ref or working directory
            if not (self.repo_path / file_path).exists():
                if ref is None or not self._file_exists_in_ref(file_path, ref):
                    raise FileNotFoundError(f"File not found: {file_path}")

            # Build git log command
            cmd = [
                "log",
                f"-n {limit}",
                "--pretty=format:%H|%an|%ae|%ad|%s",
                "--date=iso",
                "--follow",  # Follow file renames
                "--name-status",
                str(file_path)
            ]
            
            if ref:
                cmd.insert(1, ref)

            success, stdout, stderr = self._run_git_command(cmd)
            
            if not success:
                raise GitError(f"Failed to get file history: {stderr}")

            # Parse the log output
            commits = []
            current_commit = None
            
            for line in stdout.splitlines():
                if '|' in line:
                    if current_commit:
                        commits.append(current_commit)
                    hash_, author, email, date, subject = line.split('|', 4)
                    current_commit = {
                        'hash': hash_,
                        'author': author,
                        'email': email,
                        'date': date,
                        'subject': subject,
                        'changes': []
                    }
                elif line and current_commit and '\t' in line:
                    status, path = line.split('\t', 1)
                    current_commit['changes'].append({
                        'status': status[0],  # M, A, D, R, etc.
                        'path': path
                    })
            
            if current_commit:
                commits.append(current_commit)
            
            return commits

        except Exception as e:
            logger.error(f"Error getting file history for {file_path}: {e}")
            if isinstance(e, (FileNotFoundError, GitError)):
                raise
            raise GitError(f"Failed to get file history: {e}") from e

    def compare_branches(
        self,
        branch1: str,
        branch2: str,
        path: Optional[Union[str, Path]] = None,
        include_unchanged: bool = False,
    ) -> Dict[str, Any]:
        """
        Compare repository structures between two branches.

        Args:
            branch1: First branch name
            branch2: Second branch name
            path: Limit comparison to a specific subdirectory
            include_unchanged: Whether to include unchanged files in the result

        Returns:
            Dictionary containing comparison results
        """
        try:
            self._check_initialized()
            
            # Get structures for both branches
            struct1 = self.get_repository_structure(ref=branch1, path=path, recursive=True)
            struct2 = self.get_repository_structure(ref=branch2, path=path, recursive=True)
            
            # Flatten structures for easier comparison
            flat1 = self._flatten_structure(struct1)
            flat2 = self._flatten_structure(struct2)
            
            # Find differences
            result = {
                'branch1': branch1,
                'branch2': branch2,
                'added': [],
                'removed': [],
                'modified': [],
                'unchanged': []
            }
            
            all_paths = set(flat1.keys()).union(set(flat2.keys()))
            
            for path in sorted(all_paths):
                in1 = path in flat1
                in2 = path in flat2
                
                if in1 and not in2:
                    result['removed'].append(flat1[path])
                elif in2 and not in1:
                    result['added'].append(flat2[path])
                else:
                    item1 = flat1[path]
                    item2 = flat2[path]
                    
                    # Compare file metadata
                    modified = False
                    for key in ['size', 'sha', 'modified']:
                        if key in item1 and key in item2 and item1[key] != item2[key]:
                            modified = True
                            break
                    
                    if modified:
                        result['modified'].append({
                            'path': path,
                            'branch1': item1,
                            'branch2': item2
                        })
                    elif include_unchanged:
                        result['unchanged'].append(item1)
            
            return result
            
        except Exception as e:
            logger.error(f"Error comparing branches {branch1} and {branch2}: {e}")
            raise GitError(f"Failed to compare branches: {e}") from e

    def find_file_references(
        self,
        file_path: Union[str, Path],
        ref: Optional[str] = None,
        file_types: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find references to a file in the repository.
        
        Args:
            file_path: Path to the file to find references for
            ref: Git reference to search in (default: current branch)
            file_types: Limit search to specific file types (extensions)
            
        Returns:
            Dictionary mapping reference types to lists of references
        """
        try:
            self._check_initialized()
            file_path = Path(file_path)
            
            if not file_path.is_absolute():
                file_path = self.repo_path / file_path
            
            # Get the relative path for searching
            rel_path = file_path.relative_to(self.repo_path)
            
            # Find imports and references
            result = {
                'imports': self._find_imports(rel_path, ref, file_types),
                'referenced_by': self._find_referenced_by(rel_path, ref, file_types)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error finding references for {file_path}: {e}")
            raise GitError(f"Failed to find file references: {e}") from e

    def generate_structure_diagram(
        self,
        ref: Optional[str] = None,
        path: Optional[Union[str, Path]] = None,
        max_depth: Optional[int] = 3,
        include_hidden: bool = False,
    ) -> str:
        """
        Generate an ASCII tree diagram of the repository structure.
        
        Args:
            ref: Git reference to generate diagram for
            path: Subdirectory path to generate diagram for
            max_depth: Maximum depth to traverse
            include_hidden: Whether to include hidden files/directories
            
        Returns:
            ASCII string representing the repository structure
        """
        try:
            structure = self.get_repository_structure(
                ref=ref,
                path=path,
                recursive=True,
                include_hidden=include_hidden,
                max_depth=max_depth
            )
            
            if not structure or 'contents' not in structure:
                return "Empty repository or path not found"
                
            lines = []
            self._format_structure(structure['contents'], lines)
            return '\n'.join(lines)
            
        except Exception as e:
            logger.error(f"Error generating structure diagram: {e}")
            raise GitError(f"Failed to generate structure diagram: {e}") from e

    def _file_exists_in_ref(self, file_path: Union[str, Path], ref: str) -> bool:
        """Check if a file exists in a specific git reference."""
        try:
            cmd = ["ls-tree", "--name-only", ref, str(file_path)]
            success, stdout, _ = self._run_git_command(cmd)
            return success and bool(stdout.strip())
        except Exception:
            return False

    def _flatten_structure(
        self,
        structure: Dict[str, Any],
        parent_path: str = '',
        result: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Flatten a nested directory structure into a dictionary of paths to file info."""
        if result is None:
            result = {}
            
        if 'contents' in structure:
            for name, item in structure['contents'].items():
                item_path = f"{parent_path}/{name}" if parent_path else name
                if item.get('type') == 'file':
                    result[item_path] = item
                elif item.get('type') == 'directory' and 'contents' in item:
                    self._flatten_structure(item, item_path, result)
        
        return result

    def _find_imports(
        self,
        file_path: Union[str, Path],
        ref: Optional[str],
        file_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Find imports in a file."""
        try:
            content = self.get_file_content(file_path, ref=ref)
            if not content:
                return []
                
            # Simple regex to find import statements (Python, JavaScript, etc.)
            import_patterns = [
                # Python: import x, from x import y
                r'^\s*(?:from\s+([\w.]+)\s+)?import\s+([\w*.,{}\s]+)(?:\s+as\s+\w+)?\s*(?:#.*)?$',
                # JavaScript/TypeScript: import x from 'y' or import { x } from 'y'
                r'^\s*import\s+(?:[\w*{},\s]+\s+from\s+)?["\']([^"\']+)["\']\s*;?\s*(?:/\*.*\*/)?\s*$',
                # C/C++: #include "x.h" or #include <x.h>
                r'^\s*#\s*include\s+[<"]([^>"]+)[>"]\s*$',
            ]
            
            imports = []
            for line in content.splitlines():
                for pattern in import_patterns:
                    match = re.search(pattern, line, re.MULTILINE)
                    if match:
                        module = match.group(1) or match.group(2) if match.groups() > 1 else match.group(1)
                        if module:
                            imports.append({
                                'line': line.strip(),
                                'module': module.strip(),
                                'file': str(file_path)
                            })
                            break
            
            return imports
            
        except Exception as e:
            logger.warning(f"Error finding imports in {file_path}: {e}")
            return []

    def _find_referenced_by(
        self,
        file_path: Union[str, Path],
        ref: Optional[str],
        file_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Find files that reference the given file."""
        try:
            # Get the base filename without extension for searching
            file_name = Path(file_path).name
            base_name = file_name.split('.')[0]
            
            # Build git grep command to find references
            cmd = ["grep", "-l", "-I", "--perl-regexp", f"\\b{re.escape(base_name)}\\b"]
            
            # Add file type filters if specified
            if file_types:
                patterns = ' '.join(f'*.{ft.lstrip(".")}' for ft in file_types)
                cmd.extend(["--"] + patterns.split())
            
            success, stdout, _ = self._run_git_command(cmd, ref=ref)
            
            if not success or not stdout.strip():
                return []
            
            # Parse results
            references = []
            for ref_file in stdout.splitlines():
                if ref_file and ref_file != str(file_path):
                    references.append({
                        'file': ref_file,
                        'matches': [{'line': line} for line in self._get_matching_lines(ref_file, base_name, ref)]
                    })
            
            return references
            
        except Exception as e:
            logger.warning(f"Error finding references to {file_path}: {e}")
            return []

    def _get_matching_lines(
        self,
        file_path: str,
        pattern: str,
        ref: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get matching lines containing the pattern in a file."""
        try:
            content = self.get_file_content(file_path, ref=ref)
            if not content:
                return []
                
            lines = []
            for i, line in enumerate(content.splitlines(), 1):
                if re.search(rf'\b{re.escape(pattern)}\b', line):
                    lines.append({
                        'line_number': i,
                        'content': line.strip()
                    })
            return lines
            
        except Exception:
            return []

    def _format_structure(
        self,
        contents: Dict[str, Any],
        lines: List[str],
        prefix: str = ''
    ) -> None:
        """Recursively format directory structure into ASCII tree."""
        if not contents:
            return
            
        items = sorted(contents.items(), key=lambda x: (x[1].get('type') != 'directory', x[0]))
        
        for i, (name, item) in enumerate(items):
            is_last = i == len(items) - 1
            
            if item.get('type') == 'directory':
                lines.append(f"{prefix}{'└── ' if is_last else '├── '}{name}/")
                new_prefix = f"{prefix}{'    ' if is_last else '│   '}"
                if 'contents' in item:
                    self._format_structure(item['contents'], lines, new_prefix)
            else:
                # File with size
                size = item.get('size', 0)
                size_str = f" ({size} bytes)" if size else ""
                lines.append(f"{prefix}{'└── ' if is_last else '├── '}{name}{size_str}")

    def _check_initialized(self) -> None:
        """Check if the repository is initialized, raise an exception if not."""
        if not self.repo_path or not self.is_initialized():
            raise RuntimeError("Git repository is not initialized. Call initialize() first.")
