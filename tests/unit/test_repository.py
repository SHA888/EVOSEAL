"""Tests for the repository management module."""

from pathlib import Path

from evoseal.core.repository import RepositoryManager


class TestRepositoryManager:
    """Test cases for RepositoryManager class."""

    def test_clone_repository(
        self,
        repository_manager: RepositoryManager,
        test_repo: tuple[Path, "git.Repo", str],
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
        test_repo: tuple[Path, "git.Repo", str],
    ):
        """Re-cloning to an existing name overwrites it (documented behavior)."""
        repo_path, _, _ = test_repo
        test_repo_url = f"file://{repo_path}"

        # First clone should succeed.
        first = repository_manager.clone_repository(test_repo_url, "test_clone")
        assert first.exists()

        # Cloning again with the same name overwrites and succeeds.
        second = repository_manager.clone_repository(test_repo_url, "test_clone")
        assert second == first
        assert (second / "sample.py").exists()

    def test_get_repository(
        self,
        repository_manager: RepositoryManager,
        test_repo: tuple[Path, "git.Repo", str],
    ):
        """Test getting a repository instance."""
        repo_path, _, _ = test_repo
        repository_manager.clone_repository(f"file://{repo_path}", "test_get")
        repo = repository_manager.get_repository("test_get")
        assert repo is not None
        assert repo.working_dir == str(repository_manager.work_dir / "repositories" / "test_get")

    def test_checkout_branch(
        self,
        repository_manager: RepositoryManager,
        test_repo: tuple[Path, "git.Repo", str],
    ):
        """Test checking out a branch."""
        repo_path, _, _ = test_repo
        repository_manager.clone_repository(f"file://{repo_path}", "test_branch")

        # Create a new branch
        result = repository_manager.checkout_branch("test_branch", "new-feature", create=True)
        assert result

        # Verify the branch was created and checked out
        repo = repository_manager.get_repository("test_branch")
        assert repo.active_branch.name == "new-feature"

    def test_commit_changes(
        self,
        repository_manager: RepositoryManager,
        test_repo: tuple[Path, "git.Repo", str],
    ):
        """Test committing changes to a repository."""
        repo_path, _, _ = test_repo
        repository_manager.clone_repository(f"file://{repo_path}", "test_commit")

        # Create a new file
        clone_path = repository_manager.work_dir / "repositories" / "test_commit"
        (clone_path / "new_file.txt").write_text("New content")

        # Commit the changes
        result = repository_manager.commit_changes("test_commit", "Add new file")
        assert result

        # Verify the commit was created
        repo = repository_manager.get_repository("test_commit")
        assert "Add new file" in repo.head.commit.message

    def test_create_branch_from_commit(
        self,
        repository_manager: RepositoryManager,
        test_repo: tuple[Path, "git.Repo", str],
    ):
        """Test creating a branch from a specific commit."""
        repo_path, _, _ = test_repo
        repository_manager.clone_repository(f"file://{repo_path}", "test_branch_from_commit")

        # Get the initial commit
        repo = repository_manager.get_repository("test_branch_from_commit")
        initial_commit = repo.head.commit.hexsha

        # Create a new branch from the initial commit
        result = repository_manager.create_branch_from_commit(
            "test_branch_from_commit", "from-initial-commit", initial_commit
        )
        assert result

        # Verify the branch was created at the correct commit
        repo = repository_manager.get_repository("test_branch_from_commit")
        assert repo.active_branch.name == "from-initial-commit"
        assert repo.head.commit.hexsha == initial_commit

    def test_get_commit_info(
        self,
        repository_manager: RepositoryManager,
        test_repo: tuple[Path, "git.Repo", str],
    ):
        """Test getting commit information."""
        repo_path, _, _ = test_repo
        repository_manager.clone_repository(f"file://{repo_path}", "test_commit_info")

        # Get the commit info
        repo = repository_manager.get_repository("test_commit_info")
        commit_hash = repo.head.commit.hexsha

        commit_info = repository_manager.get_commit_info("test_commit_info", commit_hash)

        assert commit_info is not None
        assert commit_info["hash"] == commit_hash

    def test_get_status(
        self,
        repository_manager: RepositoryManager,
        test_repo: tuple[Path, "git.Repo", str],
    ):
        """Test getting repository status."""
        repo_path, _, _ = test_repo
        repository_manager.clone_repository(f"file://{repo_path}", "test_status")

        # Get the status
        status = repository_manager.get_status("test_status")

        assert status is not None
        assert "branch" in status
        assert "commit" in status
        assert "dirty" in status
        assert not status["dirty"]


if __name__ == "__main__":
    unittest.main()
