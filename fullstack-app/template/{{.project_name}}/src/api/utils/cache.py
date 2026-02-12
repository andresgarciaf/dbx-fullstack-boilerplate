"""Caching utilities with TTL support.

Provides decorators for function result caching with time-based expiration.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import lru_cache, wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# Global registry of named caches for clearing
_cache_registry: dict[str, Any] = {}


def cached(maxsize: int = 128) -> Callable[[F], F]:
    """Simple LRU cache decorator (wrapper around functools.lru_cache).

    Args:
        maxsize: Maximum number of cached results.

    Example:
        @cached(maxsize=256)
        def expensive_computation(x: int) -> int:
            return x ** 2
    """

    def decorator(func: F) -> F:
        cached_func = lru_cache(maxsize=maxsize)(func)
        _cache_registry[func.__name__] = cached_func
        return cached_func  # type: ignore[return-value]

    return decorator


class TTLCache:
    """Thread-safe TTL cache with LRU eviction.

    Items expire after ttl_seconds and are evicted in LRU order when maxsize is reached.
    """

    def __init__(self, maxsize: int = 128, ttl_seconds: float = 300) -> None:
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[Any, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: Any) -> Any | None:
        """Get value from cache, returning None if expired or not found."""
        with self._lock:
            if key not in self._cache:
                return None
            value, expiry = self._cache[key]
            if time.monotonic() > expiry:
                del self._cache[key]
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return value

    def set(self, key: Any, value: Any) -> None:
        """Set value in cache with TTL."""
        with self._lock:
            expiry = time.monotonic() + self.ttl_seconds
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, expiry)
            # Evict oldest if over maxsize
            while len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()

    def __contains__(self, key: Any) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None


def ttl_cache(maxsize: int = 128, ttl_seconds: float = 300, *, name: str | None = None) -> Callable[[F], F]:
    """TTL cache decorator with automatic expiration.

    Args:
        maxsize: Maximum number of cached results.
        ttl_seconds: Time-to-live in seconds for cached values.
        name: Optional name for cache (used with clear_cache).

    Example:
        @ttl_cache(ttl_seconds=60)
        def get_user_preferences(user_id: str) -> dict:
            return fetch_from_db(user_id)
    """

    def decorator(func: F) -> F:
        cache = TTLCache(maxsize=maxsize, ttl_seconds=ttl_seconds)
        cache_name = name or func.__name__
        _cache_registry[cache_name] = cache

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create cache key from args and kwargs
            key = (args, tuple(sorted(kwargs.items())))
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        # Expose cache methods on the wrapper
        wrapper.cache = cache  # type: ignore[attr-defined]
        wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]

        return wrapper  # type: ignore[return-value]

    return decorator


def clear_cache(name: str | None = None) -> None:
    """Clear a specific cache by name, or all caches if name is None.

    Args:
        name: Cache name (function name or explicit name). If None, clears all.
    """
    if name is not None:
        if name in _cache_registry:
            cache = _cache_registry[name]
            if hasattr(cache, "cache_clear"):
                cache.cache_clear()
            elif hasattr(cache, "clear"):
                cache.clear()
    else:
        for cache in _cache_registry.values():
            if hasattr(cache, "cache_clear"):
                cache.cache_clear()
            elif hasattr(cache, "clear"):
                cache.clear()
