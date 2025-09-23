"""Tests for the repository management module."""

from pathlib import Path
from typing import TYPE_CHECKING, Tuple
from unittest.mock import MagicMock, patch

import pytest

from evoseal.core.repository import RepositoryError, RepositoryManager

if TYPE_CHECKING:
    import git


class TestRepositoryManager:
    """Test cases for RepositoryManager class."""

    def test_clone_repository(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test cloning a repository."""
        repo_path, _, _ = test_repo
        test_repo_url = f"file://{repo_path}"

        # Test cloning
        clone_path = repository_manager.clone_repository(test_repo_url, "test_clone")
        assert clone_path.exists()
        assert (clone_path / ".git").exists()

        # Verify the repository was cloned to the correct location
        expected_path = repository_manager.work_dir / "repositories" / "test_clone"
        assert clone_path == expected_path

        # Verify the repository contains the expected files
        assert (clone_path / "sample.py").exists()
        assert (clone_path / "test_sample.py").exists()

    def test_clone_repository_already_exists(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test cloning to an existing repository."""
        repo_path, _, _ = test_repo
        test_repo_url = f"file://{repo_path}"

        # First clone should succeed
        result1 = repository_manager.clone_repository(test_repo_url, "test_clone")
        assert result1.exists()

        # Second clone with the same name should succeed (overwrites existing)
        result2 = repository_manager.clone_repository(test_repo_url, "test_clone")
        assert result2.exists()
        assert result2 == result1  # Same path

    def test_get_repository(self, repository_manager: RepositoryManager, test_repo: Tuple[Path, "git.Repo", str]):
        """Test getting a repository instance."""
        repo_path, _, _ = test_repo
        test_repo_url = f"file://{repo_path}"
        
        repository_manager.clone_repository(test_repo_url, "test_get")
        repo = repository_manager.get_repository("test_get")
        assert repo is not None
        assert repo.working_dir == str(repository_manager.work_dir / "repositories" / "test_get")

    def test_checkout_branch(self, repository_manager: RepositoryManager, test_repo: Tuple[Path, "git.Repo", str]):
        """Test checking out a branch."""
        repo_path, _, _ = test_repo
        test_repo_url = f"file://{repo_path}"
        
        repository_manager.clone_repository(test_repo_url, "test_branch")

        # Create a new branch
        result = repository_manager.checkout_branch("test_branch", "new-feature", create=True)
        assert result is True

        # Verify the branch was created and checked out
        repo = repository_manager.get_repository("test_branch")
        assert repo is not None
        assert repo.active_branch.name == "new-feature"

    def test_commit_changes(self, repository_manager: RepositoryManager, test_repo: Tuple[Path, "git.Repo", str]):
        """Test committing changes to a repository."""
        repo_path, _, _ = test_repo
        test_repo_url = f"file://{repo_path}"
        
        repository_manager.clone_repository(test_repo_url, "test_commit")

        # Create a new file
        repo_path = repository_manager.work_dir / "repositories" / "test_commit"
        new_file = repo_path / "new_file.txt"
        new_file.write_text("New content")

        # Commit the changes
        result = repository_manager.commit_changes("test_commit", "Add new file")

        assert result is True

        # Verify the commit was created
        repo = repository_manager.get_repository("test_commit")
        assert repo is not None
        assert "Add new file" in str(repo.head.commit.message)

    def test_create_branch_from_commit(self, repository_manager: RepositoryManager, test_repo: Tuple[Path, "git.Repo", str]):
        """Test creating a branch from a specific commit."""
        repo_path, _, _ = test_repo
        test_repo_url = f"file://{repo_path}"
        
        repository_manager.clone_repository(test_repo_url, "test_branch_from_commit")

        # Get the initial commit
        repo = repository_manager.get_repository("test_branch_from_commit")
        assert repo is not None
        initial_commit = repo.head.commit.hexsha

        # Create a new branch from the initial commit
        result = repository_manager.create_branch_from_commit(
            "test_branch_from_commit", "from-initial-commit", initial_commit
        )

        assert result is True

        # Verify the branch was created at the correct commit
        repo = repository_manager.get_repository("test_branch_from_commit")
        assert repo is not None
        assert repo.active_branch.name == "from-initial-commit"
        assert repo.head.commit.hexsha == initial_commit

    def test_get_commit_info(self, repository_manager: RepositoryManager, test_repo: Tuple[Path, "git.Repo", str]):
        """Test getting commit information."""
        repo_path, _, _ = test_repo
        test_repo_url = f"file://{repo_path}"
        
        repository_manager.clone_repository(test_repo_url, "test_commit_info")

        # Get the commit info
        repo = repository_manager.get_repository("test_commit_info")
        assert repo is not None
        commit_hash = repo.head.commit.hexsha

        commit_info = repository_manager.get_commit_info("test_commit_info", commit_hash)

        assert commit_info is not None
        assert commit_info["hash"] == commit_hash
        assert len(str(commit_info["message"])) > 0

    def test_get_status(self, repository_manager: RepositoryManager, test_repo: Tuple[Path, "git.Repo", str]):
        """Test getting repository status."""
        repo_path, _, _ = test_repo
        test_repo_url = f"file://{repo_path}"
        
        repository_manager.clone_repository(test_repo_url, "test_status")

        # Get the status
        status = repository_manager.get_status("test_status")

        assert status is not None
        assert "branch" in status
        assert "commit" in status
        assert "dirty" in status
        assert status["dirty"] is False
