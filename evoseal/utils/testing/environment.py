"""
Test environment management utilities.

Provides tools for setting up and tearing down test environments,
including temporary directories, environment variables, and test data.
"""

import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Union


class TestEnvironment:
    """Manages test environment setup and teardown.
    
    This class provides a simple interface for creating isolated test environments
    with temporary directories, environment variables, and test data.
    """
    
    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        """Initialize the test environment.
        
        Args:
            base_dir: Base directory for the test environment. If None, a temporary
                     directory will be created and automatically cleaned up.
        """
        self._base_dir = Path(base_dir) if base_dir else None
        self._temp_dir = None
        self._original_env = {}
        self._created_paths = []
        
        if not base_dir:
            self._temp_dir = tempfile.TemporaryDirectory()
            self._base_dir = Path(self._temp_dir.name)
    
    @property
    def root(self) -> Path:
        """Get the root directory of the test environment."""
        return self._base_dir
    
    def create_dir(self, path: Union[str, Path], exist_ok: bool = True) -> Path:
        """Create a directory in the test environment.
        
        Args:
            path: Path relative to the test environment root
            exist_ok: If False, raise an error if the directory already exists
            
        Returns:
            Path to the created directory
        """
        full_path = self._base_dir / path
        full_path.mkdir(parents=True, exist_ok=exist_ok)
        self._created_paths.append(full_path)
        return full_path
    
    def create_file(self, path: Union[str, Path], content: str = "") -> Path:
        """Create a file in the test environment.
        
        Args:
            path: Path relative to the test environment root
            content: Content to write to the file
            
        Returns:
            Path to the created file
        """
        full_path = self._base_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        self._created_paths.append(full_path)
        return full_path
    
    def set_env(self, env_vars: Dict[str, str]) -> None:
        """Set environment variables for the test environment.
        
        Args:
            env_vars: Dictionary of environment variables to set
        """
        for key, value in env_vars.items():
            if key not in self._original_env:
                self._original_env[key] = os.environ.get(key)
            os.environ[key] = value
    
    def cleanup(self) -> None:
        """Clean up the test environment."""
        # Restore original environment variables
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        
        # Clean up temporary directory if we created one
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None
            self._base_dir = None
        
        self._created_paths = []
        self._original_env = {}
    
    def __enter__(self) -> 'TestEnvironment':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - clean up the environment."""
        self.cleanup()


@contextmanager
def temp_environment(
    base_dir: Optional[Union[str, Path]] = None,
    env_vars: Optional[Dict[str, str]] = None,
    cleanup: bool = True
) -> Generator[TestEnvironment, None, None]:
    """Context manager for creating a temporary test environment.
    
    Args:
        base_dir: Base directory for the test environment. If None, a temporary
                 directory will be created and automatically cleaned up.
        env_vars: Dictionary of environment variables to set
        cleanup: If True, clean up the environment when exiting the context
    
    Yields:
        TestEnvironment instance
    """
    env = TestEnvironment(base_dir)
    
    try:
        if env_vars:
            env.set_env(env_vars)
        yield env
    finally:
        if cleanup:
            env.cleanup()


@contextmanager
def temp_dir() -> Generator[Path, None, None]:
    """Context manager for creating a temporary directory.
    
    The directory and its contents will be automatically removed when the context exits.
    
    Yields:
        Path to the temporary directory
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@contextmanager
def temp_file(content: str = "", suffix: str = None) -> Generator[Path, None, None]:
    """Context manager for creating a temporary file.
    
    The file will be automatically removed when the context exits.
    
    Args:
        content: Content to write to the file
        suffix: Optional suffix for the temporary file
    
    Yields:
        Path to the temporary file
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix or '', delete=False) as f:
        file_path = Path(f.name)
        if content:
            f.write(content)
    
    try:
        yield file_path
    finally:
        file_path.unlink(missing_ok=True)


@contextmanager
def temp_env_vars(env_vars: Dict[str, str]) -> Generator[None, None, None]:
    """Context manager for temporarily setting environment variables.
    
    The original environment variables will be restored when the context exits.
    
    Args:
        env_vars: Dictionary of environment variables to set
    """
    original = {}
    
    try:
        # Save original values
        for key, value in env_vars.items():
            original[key] = os.environ.get(key)
            os.environ[key] = value
        
        yield
    finally:
        # Restore original values
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class TestDataManager:
    """Manages test data for unit and integration tests."""
    
    def __init__(self, base_dir: Union[str, Path]):
        """Initialize the test data manager.
        
        Args:
            base_dir: Base directory for test data
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def get_path(self, *path_parts: str) -> Path:
        """Get the full path to a test data file or directory.
        
        Args:
            *path_parts: Path components relative to the test data directory
            
        Returns:
            Full path to the test data file or directory
        """
        return self.base_dir.joinpath(*path_parts)
    
    def create_test_data(self, structure: Dict[str, Any]) -> None:
        """Create a test data directory structure.
        
        Args:
            structure: Nested dictionary representing the directory structure.
                      Keys are file/directory names, and values are either strings
                      (file content) or dictionaries (subdirectories).
        """
        def _create_items(base_path: Path, items: Dict[str, Any]) -> None:
            for name, content in items.items():
                item_path = base_path / name
                if isinstance(content, dict):
                    item_path.mkdir(exist_ok=True)
                    _create_items(item_path, content)
                else:
                    item_path.write_text(str(content))
        
        _create_items(self.base_dir, structure)
    
    def cleanup(self) -> None:
        """Remove all test data."""
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)


def create_test_data_manager() -> TestDataManager:
    """Create a test data manager with a unique temporary directory."""
    temp_dir = Path(tempfile.mkdtemp(prefix="evoseal_test_data_"))
    return TestDataManager(temp_dir)
