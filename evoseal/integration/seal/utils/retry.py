"""
Retry utilities for SEAL system operations.
"""

import random
import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union

from ..exceptions import RateLimitError, RetryableError, TimeoutError

T = TypeVar("T")


def retry(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 5.0,
    backoff_factor: float = 2.0,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
):
    """Retry decorator with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Multiplier for exponential backoff
        exceptions: Exception(s) that trigger a retry

    Returns:
        The result of the wrapped function if successful

    Raises:
        Exception: The last exception if all retries are exhausted
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break

                    # Apply jitter to avoid thundering herd
                    sleep_time = min(delay * (backoff_factor**attempt), max_delay)
                    sleep_time *= 0.5 + random.random()  # Add jitter

                    if isinstance(e, RateLimitError):
                        # For rate limits, respect the Retry-After header if available
                        retry_after = getattr(e, "retry_after", sleep_time)
                        time.sleep(float(retry_after))
                    else:
                        time.sleep(sleep_time)

            if last_exception:
                raise last_exception
            raise RuntimeError("Retry failed but no exception was caught")

        return wrapper

    return decorator
