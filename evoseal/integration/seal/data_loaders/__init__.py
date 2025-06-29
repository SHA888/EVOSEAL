"""
Data loaders for the SEAL system.

This module provides utilities for loading, parsing, and managing knowledge
and examples from various sources and formats.
"""

from .batch import BatchLoader, default_batch_loader, load_batch
from .cache import CacheEntry, DataCache, cached, default_cache
from .loaders import (
    CSVLoader,
    DataFormat,
    DataLoader,
    JSONLoader,
    YAMLLoader,
    get_loader,
    load_data,
)

__all__ = [
    # Loaders
    'DataFormat',
    'DataLoader',
    'JSONLoader',
    'YAMLLoader',
    'CSVLoader',
    'get_loader',
    'load_data',
    # Batch processing
    'BatchLoader',
    'default_batch_loader',
    'load_batch',
    # Caching
    'CacheEntry',
    'DataCache',
    'default_cache',
    'cached',
]
