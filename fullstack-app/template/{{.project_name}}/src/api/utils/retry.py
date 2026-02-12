"""Retry utilities with exponential backoff.

Provides decorators for automatic retry of transient failures.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = field(default_factory=lambda: (Exception,))

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (1-indexed)."""
        delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = delay * (0.5 + random.random())
        return delay


# Preset configurations for common use cases
TRANSIENT_ERRORS = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)

DATABASE_ERRORS = RetryConfig(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
)


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    config: RetryConfig | None = None,
) -> Callable[[F], F]:
    """Retry decorator with exponential backoff.

    Supports both sync and async functions. Retries on specified exceptions
    with configurable delays.

    Args:
        max_attempts: Maximum number of attempts (including initial).
        initial_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay cap in seconds.
        exponential_base: Base for exponential backoff calculation.
        jitter: Add random jitter to prevent thundering herd.
        retryable_exceptions: Exception types to retry on.
        config: Optional RetryConfig to use instead of individual parameters.

    Example:
        @retry(max_attempts=3, retryable_exceptions=(ConnectionError, TimeoutError))
        async def fetch_external_data(url: str) -> dict:
            return await http_client.get(url)
    """
    if config is not None:
        cfg = config
    else:
        cfg = RetryConfig(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            retryable_exceptions=retryable_exceptions,
        )

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exception: Exception | None = None
                for attempt in range(1, cfg.max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except cfg.retryable_exceptions as e:
                        last_exception = e
                        if attempt == cfg.max_attempts:
                            logger.warning(
                                "Retry exhausted for %s after %d attempts: %s",
                                func.__name__,
                                attempt,
                                e,
                            )
                            raise
                        delay = cfg.calculate_delay(attempt)
                        logger.info(
                            "Retry %d/%d for %s after %.2fs: %s",
                            attempt,
                            cfg.max_attempts,
                            func.__name__,
                            delay,
                            e,
                        )
                        await asyncio.sleep(delay)
                # This should never be reached, but for type safety
                if last_exception:
                    raise last_exception
                raise RuntimeError("Unexpected retry state")

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(1, cfg.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except cfg.retryable_exceptions as e:
                    last_exception = e
                    if attempt == cfg.max_attempts:
                        logger.warning(
                            "Retry exhausted for %s after %d attempts: %s",
                            func.__name__,
                            attempt,
                            e,
                        )
                        raise
                    delay = cfg.calculate_delay(attempt)
                    logger.info(
                        "Retry %d/%d for %s after %.2fs: %s",
                        attempt,
                        cfg.max_attempts,
                        func.__name__,
                        delay,
                        e,
                    )
                    time.sleep(delay)
            # This should never be reached, but for type safety
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry state")

        return sync_wrapper  # type: ignore[return-value]

    return decorator
