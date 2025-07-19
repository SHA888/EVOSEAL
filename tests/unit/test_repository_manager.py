"""Unit tests for the RepositoryManager class."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from git import Repo, GitCommandError

from evoseal.core.repository import (
    RepositoryManager,
    RepositoryError,
    RepositoryNotFoundError,
    MergeError,
    ConflictError
)

class TestRepositoryManager(unittest.TestCase):
    """Test cases for RepositoryManager."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp(prefix="evoseal_test_"))
        self.manager = RepositoryManager(self.test_dir)
        
        # Create a test repository
        self.repo_url = "https://github.com/example/test-repo.git"
        self.repo_name = "test-repo"
        self.repo_path = self.test_dir / "repositories" / self.repo_name
        
        # Mock repository for testing
        self.mock_repo = MagicMock(spec=Repo)
        self.mock_repo.working_dir = str(self.repo_path)
        self.mock_repo.remotes = [MagicMock()]
        self.mock_repo.remotes[0].urls = [self.repo_url]
        self.mock_repo.is_dirty.return_value = False
        self.mock_repo.untracked_files = []
        self.mock_repo.head.is_detached = False
        self.mock_repo.active_branch.name = "main"
        self.mock_repo.head.commit.hexsha = "abc123"

    def tearDown(self):
        """Clean up test environment."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch('git.Repo.clone_from')
    def test_clone_repository(self, mock_clone):
        """Test cloning a repository."""
        # Test successful clone
        mock_clone.return_value = self.mock_repo
        result = self.manager.clone_repository(self.repo_url)
        self.assertEqual(result, self.repo_path)
        mock_clone.assert_called_once_with(self.repo_url, self.repo_path)
        
        # Test with custom name
        custom_name = "custom-repo"
        custom_path = self.test_dir / "repositories" / custom_name
        result = self.manager.clone_repository(self.repo_url, custom_name)
        self.assertEqual(result, custom_path)

    @patch('git.Repo')
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
        self.mock_repo.git.checkout.assert_called_with('-b', branch_name)

    @patch('git.Repo')
    def test_merge_branch_success(self, mock_repo):
        """Test successful branch merge."""
        # Setup
        source_branch = "feature-branch"
        target_branch = "main"
        mock_repo.return_value = self.mock_repo
        
        # Test merge
        result = self.manager.merge_branch(
            self.repo_name, source_branch, target_branch
        )
        
        # Verify
        self.assertTrue(result['success'])
        self.mock_repo.git.checkout.assert_called_with(target_branch)
        self.mock_repo.git.merge.assert_called_with(source_branch, no_ff=False, no_commit=True)

    @patch('git.Repo')
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

    @patch('git.Repo')
    def test_resolve_conflicts(self, mock_repo):
        """Test conflict resolution."""
        # Setup
        resolution = {
            "file1.txt": "resolved content 1",
            "file2.txt": "resolved content 2"
        }
        mock_repo.return_value = self.mock_repo
        
        # Test resolve conflicts
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            result = self.manager.resolve_conflicts(self.repo_name, resolution)
            
        # Verify
        self.assertTrue(result)
        self.mock_repo.git.add.assert_called()
        self.mock_repo.git.commit.assert_called_with(
            '-m', 'Resolved merge conflicts'
        )

    @patch('git.Repo')
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

    @patch('git.Repo')
    def test_get_diff(self, mock_repo):
        """Test getting diff between commits."""
        # Setup
        mock_repo.return_value = self.mock_repo
        self.mock_repo.git.diff.return_value = "diff output"
        
        # Test get diff
        result = self.manager.get_diff(
            self.repo_name, "main", "feature-branch"
        )
        
        # Verify
        self.assertEqual(result, "diff output")
        self.mock_repo.git.diff.assert_called_with("main..feature-branch")

    @patch('git.Repo')
    def test_stash_operations(self, mock_repo):
        """Test stash operations."""
        # Setup
        mock_repo.return_value = self.mock_repo
        
        # Test stash changes
        result = self.manager.stash_changes(self.repo_name, "WIP: Test stash")
        self.assertTrue(result)
        self.mock_repo.git.stash.assert_called_with('save', 'WIP: Test stash')
        
        # Test apply stash
        result = self.manager.apply_stash(self.repo_name, 'stash@{0}')
        self.assertTrue(result)
        self.mock_repo.git.stash.assert_called_with('apply', 'stash@{0}')

if __name__ == '__main__':
    unittest.main()
