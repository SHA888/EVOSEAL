"""
Tests for the repository management module.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from evoseal.core.repository import RepositoryManager


class TestRepositoryManager(unittest.TestCase):
    """Test cases for RepositoryManager class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.work_dir = Path(self.test_dir) / "work"
        self.repo_manager = RepositoryManager(self.work_dir)
        
        # Create a test git repository
        self.test_repo_path = self.work_dir / "test_repo"
        self.test_repo_path.mkdir(parents=True)
        
        # Initialize a git repository for testing
        os.system(f"git -C {self.test_repo_path} init")
        
        # Create a test file and commit it
        test_file = self.test_repo_path / "test.txt"
        test_file.write_text("Test content")
        os.system(f"git -C {self.test_repo_path} add .")
        os.system(f"git -C {self.test_repo_path} commit -m 'Initial commit'")
        
        # Store the repository URL for clone tests
        self.test_repo_url = f"file://{self.test_repo_path}"
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_clone_repository(self):
        """Test cloning a repository."""
        repo_path = self.repo_manager.clone_repository(
            self.test_repo_url, 
            "test_clone"
        )
        self.assertTrue(repo_path.exists())
        self.assertTrue((repo_path / ".git").exists())
    
    def test_get_repository(self):
        """Test getting a repository instance."""
        self.repo_manager.clone_repository(
            self.test_repo_url, 
            "test_get"
        )
        repo = self.repo_manager.get_repository("test_get")
        self.assertIsNotNone(repo)
        self.assertEqual(
            repo.working_dir, 
            str(self.work_dir / "repositories" / "test_get")
        )
    
    def test_checkout_branch(self):
        """Test checking out a branch."""
        self.repo_manager.clone_repository(
            self.test_repo_url, 
            "test_branch"
        )
        
        # Create a new branch
        result = self.repo_manager.checkout_branch(
            "test_branch", 
            "new-feature", 
            create=True
        )
        self.assertTrue(result)
        
        # Verify the branch was created and checked out
        repo = self.repo_manager.get_repository("test_branch")
        self.assertEqual(repo.active_branch.name, "new-feature")
    
    def test_commit_changes(self):
        """Test committing changes to a repository."""
        self.repo_manager.clone_repository(
            self.test_repo_url, 
            "test_commit"
        )
        
        # Create a new file
        repo_path = self.work_dir / "repositories" / "test_commit"
        new_file = repo_path / "new_file.txt"
        new_file.write_text("New content")
        
        # Commit the changes
        result = self.repo_manager.commit_changes(
            "test_commit",
            "Add new file"
        )
        
        self.assertTrue(result)
        
        # Verify the commit was created
        repo = self.repo_manager.get_repository("test_commit")
        self.assertIn("Add new file", repo.head.commit.message)


if __name__ == "__main__":
    unittest.main()
