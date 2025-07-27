"""Tests for the repository management module."""

from pathlib import Path
from typing import Tuple
from unittest.mock import MagicMock, patch

import pytest

from evoseal.core.repository import RepositoryError, RepositoryManager


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
        repository_manager.clone_repository(test_repo_url, "test_clone")

        # Second clone with the same name should raise an error
        with pytest.raises(
            RepositoryError, match="Repository 'test_clone' already exists"
        ):
            repository_manager.clone_repository(test_repo_url, "test_clone")

    def test_get_repository(self):
        """Test getting a repository instance."""
        self.repo_manager.clone_repository(self.test_repo_url, "test_get")
        repo = self.repo_manager.get_repository("test_get")
        self.assertIsNotNone(repo)
        self.assertEqual(
            repo.working_dir, str(self.work_dir / "repositories" / "test_get")
        )

    def test_checkout_branch(self):
        """Test checking out a branch."""
        self.repo_manager.clone_repository(self.test_repo_url, "test_branch")

        # Create a new branch
        result = self.repo_manager.checkout_branch(
            "test_branch", "new-feature", create=True
        )
        self.assertTrue(result)

        # Verify the branch was created and checked out
        repo = self.repo_manager.get_repository("test_branch")
        self.assertEqual(repo.active_branch.name, "new-feature")

    def test_commit_changes(self):
        """Test committing changes to a repository."""
        self.repo_manager.clone_repository(self.test_repo_url, "test_commit")

        # Create a new file
        repo_path = self.work_dir / "repositories" / "test_commit"
        new_file = repo_path / "new_file.txt"
        new_file.write_text("New content")

        # Commit the changes
        result = self.repo_manager.commit_changes("test_commit", "Add new file")

        self.assertTrue(result)

        # Verify the commit was created
        repo = self.repo_manager.get_repository("test_commit")
        self.assertIn("Add new file", repo.head.commit.message)

    def test_create_branch_from_commit(self):
        """Test creating a branch from a specific commit."""
        self.repo_manager.clone_repository(
            self.test_repo_url, "test_branch_from_commit"
        )

        # Get the initial commit
        repo = self.repo_manager.get_repository("test_branch_from_commit")
        initial_commit = repo.head.commit.hexsha

        # Create a new branch from the initial commit
        result = self.repo_manager.create_branch_from_commit(
            "test_branch_from_commit", "from-initial-commit", initial_commit
        )

        self.assertTrue(result)

        # Verify the branch was created at the correct commit
        repo = self.repo_manager.get_repository("test_branch_from_commit")
        self.assertEqual(repo.active_branch.name, "from-initial-commit")
        self.assertEqual(repo.head.commit.hexsha, initial_commit)

    def test_get_commit_info(self):
        """Test getting commit information."""
        self.repo_manager.clone_repository(self.test_repo_url, "test_commit_info")

        # Get the commit info
        repo = self.repo_manager.get_repository("test_commit_info")
        commit_hash = repo.head.commit.hexsha

        commit_info = self.repo_manager.get_commit_info("test_commit_info", commit_hash)

        self.assertIsNotNone(commit_info)
        self.assertEqual(commit_info["hash"], commit_hash)
        self.assertIn("Initial commit", commit_info["message"])

    def test_get_status(self):
        """Test getting repository status."""
        self.repo_manager.clone_repository(self.test_repo_url, "test_status")

        # Get the status
        status = self.repo_manager.get_status("test_status")

        self.assertIsNotNone(status)
        self.assertIn("branch", status)
        self.assertIn("commit", status)
        self.assertIn("dirty", status)
        self.assertFalse(status["dirty"])


if __name__ == "__main__":
    unittest.main()
