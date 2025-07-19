"""Tests for the test environment utilities."""

import os
import tempfile
from pathlib import Path

import pytest

from evoseal.utils.testing import (
    TestEnvironment,
    TestDataManager,
    temp_dir,
    temp_file,
    temp_environment,
    temp_env_vars,
    create_test_data_manager,
)


def test_test_environment_creates_temp_dir():
    """Test that TestEnvironment creates a temporary directory when none is provided."""
    with TestEnvironment() as env:
        assert env.root.exists()
        assert env.root.is_dir()


def test_test_environment_uses_existing_dir(tmp_path):
    """Test that TestEnvironment uses an existing directory when provided."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    
    with TestEnvironment(tmp_path) as env:
        assert env.root == tmp_path
        assert (env.root / "test.txt").exists()


def test_create_dir():
    """Test creating directories in the test environment."""
    with TestEnvironment() as env:
        test_dir = env.create_dir("test/directory")
        assert test_dir.exists()
        assert test_dir.is_dir()
        assert test_dir == env.root / "test" / "directory"


def test_create_file():
    """Test creating files in the test environment."""
    with TestEnvironment() as env:
        test_file = env.create_file("test/file.txt", "test content")
        assert test_file.exists()
        assert test_file.is_file()
        assert test_file.read_text() == "test content"


def test_set_env():
    """Test setting environment variables."""
    with TestEnvironment() as env:
        env.set_env({"TEST_VAR": "test_value"})
        assert os.environ["TEST_VAR"] == "test_value"
    
    # Verify cleanup
    assert "TEST_VAR" not in os.environ


def test_temp_dir():
    """Test the temp_dir context manager."""
    with temp_dir() as temp_path:
        assert temp_path.exists()
        assert temp_path.is_dir()
    
    # Directory should be deleted after context
    assert not temp_path.exists()


def test_temp_file():
    """Test the temp_file context manager."""
    with temp_file("test content", ".txt") as file_path:
        assert file_path.exists()
        assert file_path.is_file()
        assert file_path.read_text() == "test content"
    
    # File should be deleted after context
    assert not file_path.exists()


def test_temp_env_vars():
    """Test the temp_env_vars context manager."""
    # Set an initial value
    os.environ["TEST_VAR"] = "initial_value"
    
    with temp_env_vars({"TEST_VAR": "new_value", "ANOTHER_VAR": "test"}):
        assert os.environ["TEST_VAR"] == "new_value"
        assert os.environ["ANOTHER_VAR"] == "test"
    
    # Original environment should be restored
    assert os.environ["TEST_VAR"] == "initial_value"
    assert "ANOTHER_VAR" not in os.environ


def test_temp_environment():
    """Test the temp_environment context manager."""
    with temp_environment(env_vars={"TEST_VAR": "test_value"}) as env:
        # Test environment variables
        assert os.environ["TEST_VAR"] == "test_value"
        
        # Test directory creation
        test_dir = env.create_dir("test_dir")
        test_file = env.create_file("test_dir/file.txt", "content")
        
        assert test_dir.exists()
        assert test_file.exists()
    
    # Everything should be cleaned up
    assert "TEST_VAR" not in os.environ
    assert not test_file.exists()
    assert not test_dir.exists()


def test_test_data_manager():
    """Test the TestDataManager class."""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = TestDataManager(temp_dir)
        
        # Test get_path
        test_path = manager.get_path("subdir", "test.txt")
        assert str(test_path).startswith(temp_dir)
        
        # Test create_test_data
        test_structure = {
            "file1.txt": "content1",
            "subdir": {
                "file2.txt": "content2",
                "empty_dir": {}
            }
        }
        manager.create_test_data(test_structure)
        
        # Verify structure was created
        assert (Path(temp_dir) / "file1.txt").read_text() == "content1"
        assert (Path(temp_dir) / "subdir" / "file2.txt").read_text() == "content2"
        assert (Path(temp_dir) / "subdir" / "empty_dir").is_dir()
        
        # Test cleanup
        manager.cleanup()
        assert not list(Path(temp_dir).glob("*"))  # Directory should be empty


def test_create_test_data_manager():
    """Test the create_test_data_manager function."""
    with create_test_data_manager() as manager:
        assert manager.base_dir.exists()
        manager.create_test_data({"test.txt": "content"})
        assert (manager.base_dir / "test.txt").exists()
    
    # Directory should be cleaned up
    assert not manager.base_dir.exists()
