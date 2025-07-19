"""Test configuration and fixtures for the EVOSEAL test suite."""
import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture(scope="function")
def temp_workdir():
    """Create a temporary working directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def test_repo(temp_workdir):
    """Create a test git repository with sample files."""
    import git
    
    # Create a new git repository
    repo_path = temp_workdir / "test_repo"
    repo = git.Repo.init(repo_path)
    
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
    
    # Create a main branch
    repo.create_head("main")
    repo.heads.main.checkout()
    
    return repo_path
