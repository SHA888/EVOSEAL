"""Unit tests for the RepositoryManager class."""

from pathlib import Path
from typing import TYPE_CHECKING, Tuple
from unittest.mock import MagicMock, patch

import pytest
from git import GitCommandError, Repo

from evoseal.core.repository import (
    ConflictError,
    MergeError,
    RepositoryError,
    RepositoryManager,
    RepositoryNotFoundError,
)

if TYPE_CHECKING:
    import git


class TestRepositoryManager:
    """Test cases for RepositoryManager."""

    def test_clone_repository(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test cloning a repository."""
        repo_path, repo, _ = test_repo
        test_repo_url = f"file://{repo_path}"

        # Test cloning
        clone_path = repository_manager.clone_repository(test_repo_url, "test_repo")

        # Verify the repository was cloned to the correct location
        assert clone_path.exists()
        assert (clone_path / ".git").exists()
        assert clone_path == repository_manager.work_dir / "repositories" / "test_repo"

        # Verify the repository contains the expected files
        assert (clone_path / "sample.py").exists()
        assert (clone_path / "test_sample.py").exists()

    def test_get_repository(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test getting a repository instance."""
        repo_path, repo, _ = test_repo
        repo_name = "test_repo"

        # First clone the repository
        repository_manager.clone_repository(f"file://{repo_path}", repo_name)

        # Test getting the repository
        repo_instance = repository_manager.get_repository(repo_name)
        assert repo_instance is not None
        assert isinstance(repo_instance, Repo)
        assert str(repo_instance.working_dir) == str(
            repository_manager.work_dir / "repositories" / repo_name
        )

    def test_get_nonexistent_repository(self, repository_manager: RepositoryManager):
        """Test getting a repository that doesn't exist."""
        repo = repository_manager.get_repository("nonexistent_repo")
        assert repo is None

    def test_get_status(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test getting repository status."""
        repo_path, repo, _ = test_repo
        repo_name = "test_repo"

        # First clone the repository
        repository_manager.clone_repository(f"file://{repo_path}", repo_name)

        # Test getting repository status
        status = repository_manager.get_status(repo_name)

        # Verify the returned status
        assert "branch" in status
        assert "dirty" in status
        assert "commit" in status
        assert status["dirty"] is False

    def test_get_status_nonexistent_repository(self, repository_manager: RepositoryManager):
        """Test getting status for a repository that doesn't exist."""
        with pytest.raises(RepositoryNotFoundError):
            repository_manager.get_status("nonexistent_repo")

    def test_checkout_branch(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test checking out a branch."""
        repo_path, repo, _ = test_repo
        repo_name = "test_repo"

        # First clone the repository
        repository_manager.clone_repository(f"file://{repo_path}", repo_name)

        # Test creating and checking out a new branch
        result = repository_manager.checkout_branch(repo_name, "new-feature", create=True)
        assert result is True

        # Verify the branch was created and checked out
        repo_instance = repository_manager.get_repository(repo_name)
        assert repo_instance is not None
        assert repo_instance.active_branch.name == "new-feature"

    def test_commit_changes(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test committing changes to a repository."""
        repo_path, repo, _ = test_repo
        repo_name = "test_repo"

        # First clone the repository
        repository_manager.clone_repository(f"file://{repo_path}", repo_name)

        # Create a new file
        repo_dir = repository_manager.work_dir / "repositories" / repo_name
        new_file = repo_dir / "new_file.txt"
        new_file.write_text("New content")

        result = repository_manager.commit_changes(repo_name, "Add new file")
        assert result is True

        # Verify the commit was created
        repo_instance = repository_manager.get_repository(repo_name)
        assert repo_instance is not None
        assert "Add new file" in str(repo_instance.head.commit.message)

    def test_get_commit_info(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test getting commit information."""
        repo_path, repo, head_commit = test_repo
        repo_name = "test_repo"

        # First clone the repository
        repository_manager.clone_repository(f"file://{repo_path}", repo_name)

        repo_instance = repository_manager.get_repository(repo_name)
        assert repo_instance is not None
        actual_commit_hash = repo_instance.head.commit.hexsha

        # Test getting commit info
        commit_info = repository_manager.get_commit_info(repo_name, actual_commit_hash)

        # Verify the returned information
        assert commit_info is not None
        assert commit_info["hash"] == actual_commit_hash
        assert "author" in commit_info
        assert "message" in commit_info
        assert "date" in commit_info

    def test_get_branches(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test getting repository branches."""
        repo_path, repo, _ = test_repo
        repo_name = "test_repo"

        # First clone the repository
        repository_manager.clone_repository(f"file://{repo_path}", repo_name)

        # Test getting branches
        branches = repository_manager.get_branches(repo_name)

        assert isinstance(branches, list)
        assert len(branches) > 0
        assert "main" in branches

    def test_create_branch_from_commit(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test creating a branch from a specific commit."""
        repo_path, repo, _ = test_repo
        repo_name = "test_repo"

        # First clone the repository
        repository_manager.clone_repository(f"file://{repo_path}", repo_name)

        repo_instance = repository_manager.get_repository(repo_name)
        assert repo_instance is not None
        commit_hash = repo_instance.head.commit.hexsha

        # Test creating a branch from the commit
        result = repository_manager.create_branch_from_commit(
            repo_name, "from-commit-branch", commit_hash
        )
        assert result is True

        # Verify the branch was created and checked out
        repo_instance = repository_manager.get_repository(repo_name)
        assert repo_instance is not None
        assert repo_instance.active_branch.name == "from-commit-branch"
