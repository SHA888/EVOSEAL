"""
Batch loading utilities for the SEAL system.

This module provides functionality for loading multiple files in parallel
and processing them efficiently.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Type, TypeVar, Union, cast

from tqdm import tqdm

from .cache import cached
from .loaders import load_data
from .types import DataFormat

T = TypeVar("T")


class BatchLoader:
    """Utility class for batch loading and processing files."""

    def __init__(
        self, max_workers: int = 4, progress_bar: bool = True, **loader_kwargs: Any
    ) -> None:
        """Initialize the batch loader.

        Args:
            max_workers: Maximum number of worker threads
            progress_bar: Whether to show a progress bar
            **loader_kwargs: Additional arguments to pass to the loader
        """
        self.max_workers = max(max_workers, 1)
        self.progress_bar = progress_bar
        self.loader_kwargs = loader_kwargs
        self.logger = logging.getLogger(__name__)

    def load_files(
        self, file_paths: Iterable[Union[str, Path]], model: Type[T], **kwargs
    ) -> List[T]:
        """Load multiple files in parallel.

        Args:
            file_paths: Iterable of file paths to load
            model: Pydantic model to validate the data against
            **kwargs: Additional arguments to pass to the loader

        Returns:
            List of loaded and validated model instances
        """
        file_paths = list(file_paths)
        if not file_paths:
            return []

        # Merge instance kwargs with method kwargs
        loader_kwargs = {**self.loader_kwargs, **kwargs}

        results: List[T] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(
                    self._load_single_file,
                    file_path=file_path,
                    model=model,
                    **loader_kwargs,
                ): file_path
                for file_path in file_paths
            }

            # Set up progress bar if enabled
            pbar = None
            if self.progress_bar:
                pbar = tqdm(total=len(file_paths), desc="Loading files", unit="file")

            # Process results as they complete
            for future in as_completed(future_to_path):
                file_path = future_to_path[future]
                try:
                    result = future.result()
                    results.extend(result)
                except Exception as e:
                    self.logger.warning(f"Error loading file {file_path}: {str(e)}", exc_info=True)
                finally:
                    if pbar is not None:
                        pbar.update(1)

            if pbar is not None:
                pbar.close()

        return results

    def _load_single_file(self, file_path: Union[str, Path], model: Type[T], **kwargs) -> List[T]:
        """Load a single file with error handling."""
        try:
            return load_data(file_path, model, **kwargs)
        except Exception as e:
            self.logger.error(f"Failed to load {file_path}: {str(e)}")
            raise

    @cached
    def load_directory(
        self,
        directory: Union[str, Path],
        model: Type[T],
        pattern: str = "*",
        recursive: bool = True,
        **kwargs,
    ) -> List[T]:
        """Load all matching files from a directory.

        Args:
            directory: Directory to search for files
            model: Pydantic model to validate the data against
            pattern: File pattern to match (e.g., "*.json")
            recursive: Whether to search subdirectories
            **kwargs: Additional arguments to pass to the loader

        Returns:
            List of loaded and validated model instances
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        # Find all matching files
        if recursive:
            file_paths = list(directory.rglob(pattern))
        else:
            file_paths = list(directory.glob(pattern))

        self.logger.info(
            f"Found {len(file_paths)} files matching pattern '{pattern}' in {directory}"
        )

        # Filter out directories
        file_paths = [f for f in file_paths if f.is_file()]

        return self.load_files(file_paths, model, **kwargs)


# Default batch loader instance
default_batch_loader = BatchLoader()


def load_batch(
    sources: Union[str, Path, Iterable[Union[str, Path]]],
    model: Type[T],
    max_workers: int = 4,
    **kwargs,
) -> List[T]:
    """Load multiple files or directories in parallel.

    Args:
        sources: File path(s) or directory path(s) to load
        model: Pydantic model to validate the data against
        max_workers: Maximum number of worker threads
        **kwargs: Additional arguments to pass to the loader

    Returns:
        List of loaded and validated model instances
    """
    if not isinstance(sources, (str, Path)):
        sources = list(sources)
    else:
        sources = [sources]

    loader = BatchLoader(max_workers=max_workers, **kwargs)

    results: List[T] = []
    for source in sources:
        source_path = Path(source)
        if source_path.is_dir():
            results.extend(loader.load_directory(source_path, model, **kwargs))
        elif source_path.is_file():
            results.extend(loader.load_files([source_path], model, **kwargs))
        else:
            raise ValueError(f"Source not found: {source_path}")

    return results
