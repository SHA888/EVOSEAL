"""
Core data loading functionality for the SEAL system.

This module provides the main DataLoaders class that serves as a unified interface
for all data loading operations.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel

from .batch import BatchLoader, default_batch_loader, load_batch
from .cache import DataCache, cached, default_cache
from .loaders import CSVLoader, DataLoader, JSONLoader, YAMLLoader, get_loader, load_data
from .types import DataFormat, ModelType

T = TypeVar("T", bound=BaseModel)


class DataLoaders:
    """
    Unified interface for data loading operations.

    This class provides a convenient way to load data from various sources
    and formats with a consistent API.
    """

    def __init__(self, cache: Optional[DataCache] = None):
        """
        Initialize the DataLoaders with an optional cache.

        Args:
            cache: Optional DataCache instance to use for caching
        """
        self.cache = cache or default_cache
        self._loaders: Dict[DataFormat, Type[DataLoader]] = {
            DataFormat.JSON: JSONLoader,
            DataFormat.YAML: YAMLLoader,
            DataFormat.YML: YAMLLoader,  # Alias for YAML
            DataFormat.CSV: CSVLoader,
        }

    def get_loader(self, format: Union[str, DataFormat]) -> Type[DataLoader]:
        """
        Get the appropriate loader for the given format.

        Args:
            format: Format to get loader for

        Returns:
            DataLoader subclass for the specified format

        Raises:
            ValueError: If no loader is available for the format
        """
        return get_loader(format)

    @cached
    def load(
        self,
        source: Union[str, Path],
        model: Type[T],
        format: Optional[Union[str, DataFormat]] = None,
        **kwargs: Any,
    ) -> List[T]:
        """
        Load data from a source with automatic format detection.

        Args:
            source: Source to load from (file path or string content)
            model: Pydantic model to validate the data against
            format: Optional format hint (auto-detected from file extension if not provided)
            **kwargs: Additional arguments to pass to the loader

        Returns:
            List of validated model instances
        """
        return load_data(source, model, format=format, **kwargs)

    def load_batch(
        self,
        sources: Union[str, Path, List[Union[str, Path]]],
        model: Type[T],
        max_workers: int = 4,
        **kwargs: Any,
    ) -> List[T]:
        """
        Load multiple files or directories in parallel.

        Args:
            sources: File path(s) or directory path(s) to load
            model: Pydantic model to validate the data against
            max_workers: Maximum number of worker threads
            **kwargs: Additional arguments to pass to the loader

        Returns:
            List of loaded and validated model instances
        """
        return load_batch(sources, model, max_workers=max_workers, **kwargs)

    def get_batch_loader(
        self, max_workers: int = 4, progress_bar: bool = True, **kwargs: Any
    ) -> BatchLoader:
        """
        Create a BatchLoader instance with the given configuration.

        Args:
            max_workers: Maximum number of worker threads
            progress_bar: Whether to show a progress bar
            **kwargs: Additional arguments to pass to the loader

        Returns:
            Configured BatchLoader instance
        """
        return BatchLoader(max_workers=max_workers, progress_bar=progress_bar, **kwargs)


# Default instance for convenience
default_data_loaders = DataLoaders()
