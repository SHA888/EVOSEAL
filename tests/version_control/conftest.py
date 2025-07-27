"""Pytest configuration and fixtures for version control tests."""

import os
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from evoseal.utils.version_control.cmd_git import CmdGit


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create and clean up a temporary directory for tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="evoseal-test-"))
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def git_repo(temp_dir: Path) -> CmdGit:
    """Create a Git repository for testing."""
    repo = CmdGit(repo_path=temp_dir)
    repo.initialize()
    return repo


@pytest.fixture
def git_repo_with_commit(git_repo: CmdGit) -> CmdGit:
    """Create a Git repository with an initial commit."""
    # Create and commit a README file
    readme = git_repo.repo_path / "README.md"
    readme.write_text("# Test Repository\n")

    # Configure user for the test repository
    git_repo._run_git_command(["config", "user.name", "Test User"])
    git_repo._run_git_command(["config", "user.email", "test@example.com"])

    # Stage and commit
    git_repo._run_git_command(["add", "README.md"])
    git_repo._run_git_command(["commit", "-m", "Initial commit"])

    return git_repo


@pytest.fixture
def git_remote_repo(temp_dir: Path) -> Path:
    """Create a bare Git repository to use as a remote."""
    remote_path = temp_dir / "remote.git"

    # Ensure the directory exists and is empty
    if remote_path.exists():
        shutil.rmtree(remote_path)

    # Create the directory with parents
    remote_path.mkdir(parents=True, exist_ok=True)

    # Verify the directory was created
    assert (
        remote_path.exists() and remote_path.is_dir()
    ), f"Failed to create directory: {remote_path}"

    try:
        # Initialize bare repository
        repo = CmdGit(repo_path=remote_path)
        result = repo.initialize(bare=True)
        assert result, f"Failed to initialize bare repository at {remote_path}"

        # Configure user for the test repository
        repo._run_git_command(["config", "user.name", "Test User"])
        repo._run_git_command(["config", "user.email", "test@example.com"])

        return remote_path
    except Exception as e:
        # Clean up if something goes wrong
        if remote_path.exists():
            shutil.rmtree(remote_path, ignore_errors=True)
        raise RuntimeError(f"Failed to create git remote repo at {remote_path}: {e}")
