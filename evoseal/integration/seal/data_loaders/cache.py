"""
Caching utilities for data loaders.

This module provides caching mechanisms to improve performance when loading
frequently accessed data.
"""

import hashlib
import json
import os
import pickle  # nosec - Using in a controlled environment with trusted cache files
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar, Union, cast

from pydantic import BaseModel

T = TypeVar("T")


class CacheEntry(BaseModel):
    """A single cache entry with expiration."""

    data: Any
    expires_at: Optional[datetime] = None
    created_at: datetime
    version: str = "1.0"

    @property
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


class DataCache:
    """In-memory and filesystem cache for data loaders."""

    def __init__(
        self,
        cache_dir: Optional[Union[str, Path]] = None,
        default_ttl: Optional[timedelta] = None,
        max_size: int = 1000,
    ) -> None:
        """Initialize the cache.

        Args:
            cache_dir: Directory for persistent cache storage. If None, only in-memory caching is used.
            default_ttl: Default time-to-live for cache entries.
            max_size: Maximum number of in-memory cache entries.
        """
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.default_ttl = default_ttl or timedelta(hours=1)
        self.max_size = max_size

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, key: str) -> str:
        """Generate a cache key from a string."""
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _get_cache_path(self, key: str) -> Optional[Path]:
        """Get the filesystem path for a cache key."""
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"{self._get_cache_key(key)}.pkl"

    def get(self, key: str) -> Any:
        """Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        # Try memory cache first
        entry = self.memory_cache.get(key)
        if entry is not None:
            if entry.is_expired:
                del self.memory_cache[key]
                return None
            return entry.data

        # Try filesystem cache
        cache_path = self._get_cache_path(key)
        if cache_path and cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    entry: CacheEntry = pickle.load(
                        f
                    )  # nosec - Using trusted cache files in a controlled environment
                    if entry.is_expired:
                        cache_path.unlink()
                        return None
                    # Promote to memory cache
                    self.memory_cache[key] = entry
                    return entry.data
            except (pickle.PickleError, EOFError, AttributeError):
                # Corrupted cache file
                cache_path.unlink()

        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None,
        persist: bool = False,
    ) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache (must be picklable if persisting)
            ttl: Time to live for the cache entry
            persist: Whether to persist to disk
        """
        expires_at = None
        if ttl is not None:
            expires_at = datetime.now() + ttl
        elif self.default_ttl is not None:
            expires_at = datetime.now() + self.default_ttl

        entry = CacheEntry(data=value, expires_at=expires_at, created_at=datetime.now())

        # Update memory cache
        self.memory_cache[key] = entry

        # Enforce max size
        if len(self.memory_cache) > self.max_size:
            # Remove the oldest entry
            oldest_key = next(iter(self.memory_cache))
            self.memory_cache.pop(oldest_key, None)

        # Persist to disk if requested
        if persist and self.cache_dir is not None:
            cache_path = self._get_cache_path(key)
            if cache_path:
                try:
                    with open(cache_path, "wb") as f:
                        pickle.dump(entry, f)
                except (pickle.PickleError, IOError):
                    # Silently fail on cache write errors
                    pass

    def clear(self, expired_only: bool = False) -> None:
        """Clear the cache.

        Args:
            expired_only: If True, only remove expired entries
        """
        if expired_only:
            # Clear expired entries from memory
            expired_keys = [k for k, v in self.memory_cache.items() if v.is_expired]
            for key in expired_keys:
                self.memory_cache.pop(key, None)

            # Clear expired files
            if self.cache_dir:
                for cache_file in self.cache_dir.glob("*.pkl"):
                    try:
                        with open(cache_file, "rb") as f:
                            entry: CacheEntry = pickle.load(
                                f
                            )  # nosec - Using trusted cache files in a controlled environment
                            if entry.is_expired:
                                cache_file.unlink()
                    except (pickle.PickleError, EOFError, AttributeError):
                        # Corrupted cache file
                        cache_file.unlink()
        else:
            # Clear everything
            self.memory_cache.clear()
            if self.cache_dir:
                for cache_file in self.cache_dir.glob("*.pkl"):
                    cache_file.unlink()


# Default global cache instance
default_cache = DataCache(
    cache_dir=Path.home() / ".evoseal" / "cache" / "data_loaders",
    default_ttl=timedelta(hours=24),
    max_size=1000,
)


def cached(
    func: Optional[Callable[..., T]] = None,
    key: Optional[str] = None,
    ttl: Optional[timedelta] = None,
    cache: Optional[DataCache] = None,
    use_args: bool = True,
    use_kwargs: bool = True,
    persist: bool = False,
) -> Callable[..., T]:
    """Decorator to cache function results.

    Args:
        func: Function to decorate
        key: Custom cache key (defaults to function name)
        ttl: Time to live for cache entries
        cache: Cache instance to use (defaults to default_cache)
        use_args: Include positional arguments in cache key
        use_kwargs: Include keyword arguments in cache key
        persist: Whether to persist the cache to disk

    Returns:
        Decorated function with caching
    """
    if cache is None:
        cache = default_cache

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Generate cache key
            cache_key_parts = [key or func.__name__]

            if use_args and args:
                cache_key_parts.append(json.dumps(args, sort_keys=True))

            if use_kwargs and kwargs:
                cache_key_parts.append(json.dumps(kwargs, sort_keys=True))

            cache_key = "::".join(str(part) for part in cache_key_parts)

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cast(T, cached_result)

            # Not in cache, call the function
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl=ttl, persist=persist)

            return result

        return wrapper

    # Handle both @cached and @cached() syntax
    if func is not None:
        return decorator(func)
    return decorator
