"""Retry utilities for tool HTTP calls.

Provides a decorator that retries on transient network errors with
exponential backoff. Does NOT retry on 4xx errors or rate limits.
"""

import functools
import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Transient errors worth retrying
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    ConnectionError,
    TimeoutError,
)


def with_retry(max_retries: int = 2, base_delay: float = 2.0):
    """Decorator that retries a function on transient network errors.

    Args:
        max_retries: Maximum number of retry attempts (default 2).
        base_delay: Base delay in seconds, doubled each retry (default 2s → 4s).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"[retry] {func.__name__} attempt {attempt + 1}/{max_retries + 1} "
                            f"failed with {type(e).__name__}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.warning(
                            f"[retry] {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                except httpx.HTTPStatusError as e:
                    # Don't retry 4xx errors
                    if 400 <= e.response.status_code < 500:
                        raise
                    # Retry 5xx errors
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"[retry] {func.__name__} got HTTP {e.response.status_code}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.warning(
                            f"[retry] {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
            raise last_exception
        return wrapper
    return decorator


def httpx_get_with_retry(url: str, max_retries: int = 2, **kwargs) -> httpx.Response:
    """Convenience wrapper for httpx.get with retry logic.

    Args:
        url: URL to fetch.
        max_retries: Number of retries on transient errors.
        **kwargs: Passed to httpx.get (headers, timeout, follow_redirects, etc.)

    Returns:
        httpx.Response

    Raises:
        The last exception if all retries fail.
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            response = httpx.get(url, **kwargs)
            # Raise on 5xx for retry
            if response.status_code >= 500 and attempt < max_retries:
                logger.warning(
                    f"[retry] GET {url} returned {response.status_code}. "
                    f"Retrying ({attempt + 1}/{max_retries + 1})..."
                )
                time.sleep(2.0 * (2 ** attempt))
                continue
            return response
        except RETRYABLE_EXCEPTIONS as e:
            last_exception = e
            if attempt < max_retries:
                delay = 2.0 * (2 ** attempt)
                logger.warning(
                    f"[retry] GET {url} failed with {type(e).__name__}. "
                    f"Retrying in {delay:.1f}s ({attempt + 1}/{max_retries + 1})..."
                )
                time.sleep(delay)
            else:
                logger.warning(f"[retry] GET {url} failed after {max_retries + 1} attempts: {e}")
                raise
    raise last_exception


def httpx_post_with_retry(url: str, max_retries: int = 2, **kwargs) -> httpx.Response:
    """Convenience wrapper for httpx.post with retry logic."""
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            response = httpx.post(url, **kwargs)
            if response.status_code >= 500 and attempt < max_retries:
                logger.warning(
                    f"[retry] POST {url} returned {response.status_code}. "
                    f"Retrying ({attempt + 1}/{max_retries + 1})..."
                )
                time.sleep(2.0 * (2 ** attempt))
                continue
            return response
        except RETRYABLE_EXCEPTIONS as e:
            last_exception = e
            if attempt < max_retries:
                delay = 2.0 * (2 ** attempt)
                logger.warning(
                    f"[retry] POST {url} failed with {type(e).__name__}. "
                    f"Retrying in {delay:.1f}s ({attempt + 1}/{max_retries + 1})..."
                )
                time.sleep(delay)
            else:
                logger.warning(f"[retry] POST {url} failed after {max_retries + 1} attempts: {e}")
                raise
    raise last_exception
