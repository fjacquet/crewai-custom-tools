"""
Cache manager for API results to reduce rate limits and improve performance.

This module provides a simple file-based caching system for API calls
to avoid repeated requests and respect rate limits.
"""

from functools import wraps
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Configure standard logger
logger = logging.getLogger(__name__)


class CacheManager:
    """Simple file-based cache manager for API results."""

    def __init__(self, cache_dir: str | Path = "cache", default_ttl: int = 3600):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live in seconds (1 hour default)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.default_ttl = default_ttl

    def _get_cache_path(self, key: str) -> Path:
        """Get the cache file path for a given key."""
        # Create a safe filename from the key, appending its MD5 hash to prevent collisions and OS limits
        key_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
        safe_key = "".join(c for c in key[:50] if c.isalnum() or c in ("-", "_", ".")).rstrip()
        return self.cache_dir / f"{safe_key}_{key_hash}.json"

    def get(self, key: str, ttl: int | None = None) -> Any | None:
        """
        Get a value from cache if it exists and hasn't expired.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds (uses default if None)

        Returns:
            Cached value if found and valid, None otherwise
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                cache_data = json.load(f)

            # Check if cache has expired
            cached_time = datetime.fromisoformat(cache_data["timestamp"])
            ttl_seconds = ttl if ttl is not None else self.default_ttl

            if datetime.now() - cached_time > timedelta(seconds=ttl_seconds):
                # Cache expired, remove file
                try:
                    cache_path.unlink()
                except FileNotFoundError:
                    pass
                return None

            return cache_data["data"]

        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, KeyError, ValueError):
            # Invalid cache file, remove it
            try:
                cache_path.unlink()
            except FileNotFoundError:
                pass
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Store a value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        cache_path = self._get_cache_path(key)

        cache_data = {"timestamp": datetime.now().isoformat(), "data": value}

        try:
            with open(cache_path, "w") as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            # If caching fails, just continue without caching
            logger.warning(f"Failed to cache data for key {key}: {e}")

    def clear(self) -> None:
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except FileNotFoundError:
                pass

    def clear_expired(self, ttl: int | None = None) -> int:
        """
        Clear expired cache entries.

        Args:
            ttl: Time-to-live in seconds (uses default if None)

        Returns:
            Number of expired entries removed
        """
        ttl_seconds = ttl if ttl is not None else self.default_ttl
        removed_count = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file) as f:
                    cache_data = json.load(f)

                cached_time = datetime.fromisoformat(cache_data["timestamp"])

                if datetime.now() - cached_time > timedelta(seconds=ttl_seconds):
                    try:
                        cache_file.unlink()
                    except FileNotFoundError:
                        pass
                    removed_count += 1

            except FileNotFoundError:
                pass
            except (json.JSONDecodeError, KeyError, ValueError):
                # Invalid cache file, remove it
                try:
                    cache_file.unlink()
                except FileNotFoundError:
                    pass
                removed_count += 1

        return removed_count


# Global cache instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cache_api_call(key: str, ttl: int = 3600):
    """
    Decorator to cache API call results.

    Args:
        key: Base cache key (will be combined with function args)
        ttl: Time-to-live in seconds
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # Create a unique cache key based on function name and arguments
            serialized = f"{args}_{sorted(kwargs.items())}"
            args_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
            cache_key = f"{key}_{func.__name__}_{args_hash}"

            # Try to get from cache first
            cached_result = cache.get(cache_key, ttl)
            if cached_result is not None:
                return cached_result

            # Call the function and cache the result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)

            return result

        return wrapper

    return decorator
