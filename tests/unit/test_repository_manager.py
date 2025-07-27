"""Unit tests for the RepositoryManager class."""

from pathlib import Path
from typing import Tuple
from unittest.mock import MagicMock, call, patch

import pytest
from git import GitCommandError, Repo

from evoseal.core.repository import (
    ConflictError,
    MergeError,
    RepositoryError,
    RepositoryManager,
    RepositoryNotFoundError,
)


class TestRepositoryManager:
    """Test cases for RepositoryManager."""

    def test_clone_repository(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
        monkeypatch,
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

        # Verify the repository is in the manager's cache
        assert "test_repo" in repository_manager._repositories

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
        with pytest.raises(RepositoryNotFoundError):
            repository_manager.get_repository("nonexistent_repo")

    def test_remove_repository(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
        monkeypatch,
    ):
        """Test removing a repository."""
        repo_path, repo, _ = test_repo
        repo_name = "test_repo"

        # First clone the repository
        repository_manager.clone_repository(f"file://{repo_path}", repo_name)

        # Mock shutil.rmtree to prevent actual deletion
        mock_rmtree = MagicMock()
        monkeypatch.setattr("shutil.rmtree", mock_rmtree)

        # Test removing the repository
        repository_manager.remove_repository(repo_name)

        # Verify the repository was removed from the manager
        assert repo_name not in repository_manager._repositories

        # Verify rmtree was called with the correct path
        expected_path = repository_manager.work_dir / "repositories" / repo_name
        mock_rmtree.assert_called_once_with(str(expected_path))

        # Test removing a non-existent repository
        with pytest.raises(RepositoryNotFoundError):
            repository_manager.remove_repository("nonexistent_repo")

    def test_get_repository_info(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test getting repository information."""
        repo_path, repo, head_commit = test_repo
        repo_name = "test_repo"

        # First clone the repository
        repository_manager.clone_repository(f"file://{repo_path}", repo_name)

        # Test getting repository info
        info = repository_manager.get_repository_info(repo_name)

        # Verify the returned information
        assert info["name"] == repo_name
        assert info["path"] == str(
            repository_manager.work_dir / "repositories" / repo_name
        )
        assert info["branch"] == "main"
        assert info["commit"] == head_commit
        assert info["dirty"] is False

    def test_get_repositories(
        self,
        repository_manager: RepositoryManager,
        test_repo: Tuple[Path, "git.Repo", str],
    ):
        """Test getting all repositories."""
        repo_path, repo, _ = test_repo

        # Add test repositories
        repository_manager.clone_repository(f"file://{repo_path}", "repo1")
        repository_manager.clone_repository(f"file://{repo_path}", "repo2")

        # Test getting all repositories
        repos = repository_manager.get_repositories()

        # Verify the returned repositories
        assert len(repos) == 2
        assert "repo1" in repos
        assert "repo2" in repos
        assert isinstance(repos["repo1"], dict)
        assert isinstance(repos["repo2"], dict)

    @patch("git.Repo")
    def test_checkout_branch(self, mock_repo):
        """Test checking out a branch."""
        # Setup
        branch_name = "feature-branch"
        mock_repo.return_value = self.mock_repo

        # Test checkout existing branch
        result = self.manager.checkout_branch(self.repo_name, branch_name)
        self.assertTrue(result)
        self.mock_repo.git.checkout.assert_called_once_with(branch_name)

        # Test create new branch
        self.manager.checkout_branch(self.repo_name, branch_name, create=True)
        self.mock_repo.git.checkout.assert_called_with("-b", branch_name)

    @patch("git.Repo")
    def test_merge_branch_success(self, mock_repo):
        """Test successful branch merge."""
        # Setup
        source_branch = "feature-branch"
        target_branch = "main"
        mock_repo.return_value = self.mock_repo

        # Test merge
        result = self.manager.merge_branch(self.repo_name, source_branch, target_branch)

        # Verify
        self.assertTrue(result["success"])
        self.mock_repo.git.checkout.assert_called_with(target_branch)
        self.mock_repo.git.merge.assert_called_with(
            source_branch, no_ff=False, no_commit=True
        )

    @patch("git.Repo")
    def test_merge_branch_conflict(self, mock_repo):
        """Test merge with conflicts."""
        # Setup
        source_branch = "feature-branch"
        target_branch = "main"

        # Make merge raise a conflict error
        self.mock_repo.git.merge.side_effect = GitCommandError("merge", "CONFLICT")
        self.mock_repo.index.unmerged = ["file1.txt", "file2.txt"]
        mock_repo.return_value = self.mock_repo

        # Test merge with conflict
        with self.assertRaises(ConflictError) as cm:
            self.manager.merge_branch(self.repo_name, source_branch, target_branch)

        # Verify conflict details
        self.assertEqual(len(cm.exception.conflicts), 2)
        self.assertIn("file1.txt", cm.exception.conflicts)

    @patch("git.Repo")
    def test_resolve_conflicts(self, mock_repo):
        """Test conflict resolution."""
        # Setup
        resolution = {
            "file1.txt": "resolved content 1",
            "file2.txt": "resolved content 2",
        }
        mock_repo.return_value = self.mock_repo

        # Test resolve conflicts
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            result = self.manager.resolve_conflicts(self.repo_name, resolution)

        # Verify
        self.assertTrue(result)
        self.mock_repo.git.add.assert_called()
        self.mock_repo.git.commit.assert_called_with("-m", "Resolved merge conflicts")

    @patch("git.Repo")
    def test_create_tag(self, mock_repo):
        """Test creating a tag."""
        # Setup
        tag_name = "v1.0.0"
        mock_repo.return_value = self.mock_repo

        # Test create tag
        result = self.manager.create_tag(
            self.repo_name, tag_name, "Release 1.0.0", "abc123"
        )

        # Verify
        self.assertTrue(result)
        self.mock_repo.create_tag.assert_called_with(
            tag_name, ref="abc123", message="Release 1.0.0"
        )

    @patch("git.Repo")
    def test_get_diff(self, mock_repo):
        """Test getting diff between commits."""
        # Setup
        mock_repo.return_value = self.mock_repo
        self.mock_repo.git.diff.return_value = "diff output"

        # Test get diff
        result = self.manager.get_diff(self.repo_name, "main", "feature-branch")

        # Verify
        self.assertEqual(result, "diff output")
        self.mock_repo.git.diff.assert_called_with("main..feature-branch")

    @patch("git.Repo")
    def test_stash_operations(self, mock_repo):
        """Test stash operations."""
        # Setup
        mock_repo.return_value = self.mock_repo

        # Test stash changes
        result = self.manager.stash_changes(self.repo_name, "WIP: Test stash")
        self.assertTrue(result)
        self.mock_repo.git.stash.assert_called_with("save", "WIP: Test stash")

        # Test apply stash
        result = self.manager.apply_stash(self.repo_name, "stash@{0}")
        self.assertTrue(result)
        self.mock_repo.git.stash.assert_called_with("apply", "stash@{0}")


if __name__ == "__main__":
    unittest.main()
