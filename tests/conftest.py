"""Test configuration and fixtures for the EVOSEAL test suite."""
import os
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator

# Add the project root to the Python path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="function")
def temp_workdir() -> Generator[Path, None, None]:
    """Create a temporary working directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def test_repo(temp_workdir: Path) -> Generator[Path, None, None]:
    """Create a test git repository with sample files."""
    import git
    
    # Create a new git repository
    repo_path = temp_workdir / "test_repo"
    repo = git.Repo.init(repo_path)
    
    # Configure git user for the test repository
    with repo.config_writer() as git_config:
        git_config.set_value("user", "name", "Test User")
        git_config.set_value("user", "email", "test@example.com")
    
    # Create a sample Python file
    sample_file = repo_path / "sample.py"
    sample_file.write_text("""def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
""")
    
    # Create a test file
    test_file = repo_path / "test_sample.py"
    test_file.write_text("""import unittest
from sample import add, subtract

class TestMath(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(1, 2), 3)
    
    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)

if __name__ == "__main__":
    unittest.main()
""")
    
    # Add and commit the files
    repo.index.add(["sample.py", "test_sample.py"])
    repo.index.commit("Initial commit")
    
    # Create a main branch and make an initial commit
    if "main" not in repo.heads:
        repo.create_head("main")
    repo.heads.main.checkout()
    
    # Create a test branch
    if "test-branch" not in repo.heads:
        repo.create_head("test-branch")
    
    # Make a second commit on the main branch
    another_file = repo_path / "another_file.txt"
    another_file.write_text("This is another file.")
    repo.index.add([str(another_file)])
    repo.index.commit("Add another file")
    
    # Store the commit hash for reference
    head_commit = repo.head.commit.hexsha
    
    # Create a tag
    repo.create_tag("v1.0.0", message="Test tag")
    
    # Return both the path and the repository object for more flexible testing
    return repo_path, repo, head_commit


@pytest.fixture(scope="function")
def bare_test_repo(test_repo: Tuple[Path, 'git.Repo', str]) -> Path:
    """Create a bare clone of the test repository for testing remote operations."""
    import git
    
    repo_path, repo, _ = test_repo
    bare_repo_path = repo_path.parent / "test_repo_bare.git"
    
    # Create a bare clone
    bare_repo = git.Repo.clone_from(
        str(repo_path),
        str(bare_repo_path),
        bare=True
    )
    
    # Update the test repo to have the bare repo as a remote
    origin = repo.create_remote("origin", str(bare_repo_path))
    origin.push(all=True)
    
    yield bare_repo_path
    
    # Cleanup
    if bare_repo_path.exists():
        bare_repo.close()
        shutil.rmtree(bare_repo_path, ignore_errors=True)


@pytest.fixture(scope="function")
def repository_manager(temp_workdir: Path) -> 'RepositoryManager':
    """Create a RepositoryManager instance with a temporary working directory."""
    from evoseal.core.repository import RepositoryManager
    return RepositoryManager(temp_workdir)


@pytest.fixture(scope="function")
def mock_repository() -> 'MagicMock':
    """Create a mock repository for testing."""
    from unittest.mock import MagicMock
    
    mock_repo = MagicMock()
    mock_repo.working_dir = "/mock/repo/path"
    mock_repo.remotes = [MagicMock()]
    mock_repo.remotes[0].urls = ["https://github.com/example/mock-repo.git"]
    mock_repo.is_dirty.return_value = False
    mock_repo.untracked_files = []
    mock_repo.head.is_detached = False
    mock_repo.active_branch.name = "main"
    mock_repo.head.commit.hexsha = "a1b2c3d4e5f6"
    
    return mock_repo
