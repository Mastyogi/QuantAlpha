import asyncio
import functools
import logging
from typing import Type, Tuple

logger = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Exponential backoff retry decorator for async functions."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    wait = min(delay * (exponential_base ** (attempt - 1)), max_delay)
                    logger.warning(
                        f"{func.__name__} attempt {attempt} failed: {e}. "
                        f"Retrying in {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
            raise last_exception

        return wrapper

    return decorator


def sync_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Synchronous retry decorator with exponential backoff."""
    import time

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        raise
                    wait = min(
                        initial_delay * (exponential_base ** (attempt - 1)), max_delay
                    )
                    logger.warning(
                        f"{func.__name__} attempt {attempt} failed: {e}. "
                        f"Retrying in {wait:.1f}s"
                    )
                    time.sleep(wait)
            raise last_exception

        return wrapper

    return decorator
