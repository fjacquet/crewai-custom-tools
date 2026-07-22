"""
Cache manager for API results to reduce rate limits and improve performance.

This module provides a simple file-based and memory caching system for API calls
to avoid repeated requests and respect rate limits using SHA-256.
"""

import contextlib
import hashlib
import json
import logging
import os
import time
from functools import wraps
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("crewai_custom_tools.cache")


class CacheManager:
    """Simple file and memory-based cache manager for API results using SHA-256."""

    def __init__(self, cache_dir: str | Path = ".cache", default_ttl: int = 3600):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live in seconds
        """
        self.cache_dir = Path(cache_dir)
        self.default_ttl = default_ttl
        self.memory_cache = {}
        self.cache_dir.mkdir(exist_ok=True, parents=True)

    def _get_filename(self, key: str) -> str:
        """Secure, modern SHA-256 hashing to map keys into safe file paths without MD5."""
        hasher = hashlib.sha256(key.encode("utf-8"))
        return os.path.join(
            str(self.cache_dir), f"cache_{hasher.hexdigest()[:32]}.json"
        )

    def _get_cache_path(self, key: str) -> Path:
        """Get the cache file path as a Path object for a given key."""
        return Path(self._get_filename(key))

    def get(self, key: str, ttl: int | None = None) -> Any | None:
        """
        Get a value from cache if it exists and hasn't expired.

        Checks memory cache first, then falls back to disk.
        """
        # Memory check first
        if key in self.memory_cache:
            filepath = self._get_cache_path(key)
            try:
                mtime = filepath.stat().st_mtime
                cached_data = self.memory_cache[key]
                if len(cached_data) == 4 and cached_data[3] != mtime:
                    # Invalidate memory cache since file has changed on disk
                    del self.memory_cache[key]
                else:
                    val, timestamp, expiry = (
                        cached_data[0],
                        cached_data[1],
                        cached_data[2],
                    )

                    # If get is called with an explicit ttl, use that to determine expiration
                    if ttl is not None:
                        if time.time() - timestamp >= ttl:
                            del self.memory_cache[key]
                            with contextlib.suppress(OSError):
                                filepath.unlink()
                            return None
                        return val

                    # Otherwise, check stored absolute expiry
                    if expiry is None or expiry > time.time():
                        return val
                    else:
                        del self.memory_cache[key]
                        with contextlib.suppress(OSError):
                            filepath.unlink()
                        return None
            except OSError:
                # File deleted or cannot be stat'ed, invalidate memory cache
                del self.memory_cache[key]
                return None

        filepath = self._get_cache_path(key)
        if not filepath.exists():
            return None

        try:
            mtime = filepath.stat().st_mtime
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            val = data.get("value")
            timestamp = data.get("timestamp")
            expiry = data.get("expiry")

            # Ensure defaults if they are missing
            if timestamp is None:
                timestamp = time.time()

            if ttl is not None:
                if time.time() - timestamp >= ttl:
                    with contextlib.suppress(OSError):
                        filepath.unlink()
                    return None
                self.memory_cache[key] = (val, timestamp, expiry, mtime)
                return val

            if expiry is None or expiry > time.time():
                self.memory_cache[key] = (val, timestamp, expiry, mtime)
                return val
            else:
                with contextlib.suppress(OSError):
                    filepath.unlink()
        except (json.JSONDecodeError, OSError, KeyError, ValueError) as e:
            logger.warning(f"Purging corrupted cache file {filepath} due to error: {e}")
            with contextlib.suppress(OSError):
                filepath.unlink()
        return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value in cache with optional TTL."""
        effective_ttl = ttl if ttl is not None else self.default_ttl
        timestamp = time.time()
        expiry = timestamp + effective_ttl if effective_ttl is not None else None

        filepath = self._get_cache_path(key)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({"value": value, "timestamp": timestamp, "expiry": expiry}, f)
            mtime = filepath.stat().st_mtime
            self.memory_cache[key] = (value, timestamp, expiry, mtime)
        except OSError as e:
            logger.error(f"Failed to write cache file {filepath}: {e}")

    def clear(self) -> None:
        """Clear all cached data."""
        self.memory_cache.clear()
        for filepath in self.cache_dir.glob("*.json"):
            with contextlib.suppress(OSError):
                filepath.unlink()

    def clear_expired(self, ttl: int | None = None) -> int:
        """Clear expired cache entries from memory and disk."""
        removed_count = 0

        # Clear memory cache expired entries to keep it clean
        expired_mem_keys = []
        for key, cached_data in list(self.memory_cache.items()):
            timestamp, expiry = cached_data[1], cached_data[2]
            if ttl is not None:
                if time.time() - timestamp >= ttl:
                    expired_mem_keys.append(key)
            elif expiry is not None and expiry <= time.time():
                expired_mem_keys.append(key)

        for key in expired_mem_keys:
            self.memory_cache.pop(key, None)

        # Clear expired files from disk
        for filepath in list(self.cache_dir.glob("*.json")):
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                timestamp = data.get("timestamp")
                expiry = data.get("expiry")

                if timestamp is None:
                    timestamp = time.time()

                is_expired = False
                if ttl is not None:
                    if time.time() - timestamp >= ttl:
                        is_expired = True
                elif expiry is not None and expiry <= time.time():
                    is_expired = True
                elif expiry is None:
                    effective_ttl = self.default_ttl
                    if (
                        effective_ttl is not None
                        and time.time() - timestamp >= effective_ttl
                    ):
                        is_expired = True

                if is_expired:
                    with contextlib.suppress(OSError):
                        filepath.unlink()
                    removed_count += 1
            except (json.JSONDecodeError, OSError, KeyError, ValueError):
                # Invalid or corrupt cache file, remove it
                with contextlib.suppress(OSError):
                    filepath.unlink()
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
            # Handle instance/class methods cleanly by ignoring the dynamic memory address of 'self' (args[0])
            args_to_serialize = args
            if (
                args
                and hasattr(args[0], "__class__")
                and not isinstance(args[0], (str, int, float, dict, list, set, tuple))
            ):
                # If first arg is a custom object instance, replace it with its class name for deterministic keys
                args_to_serialize = (args[0].__class__.__name__, *args[1:])

            serialized = f"{args_to_serialize}_{sorted(kwargs.items())}"
            args_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
            cache_key = f"{key}_{func.__name__}_{args_hash}"

            # Try to get from cache first
            cached_result = cache.get(cache_key, ttl)
            if cached_result is not None:
                return cached_result

            # Call the function and cache the result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator
