import pytest
import time
from pathlib import Path
from crewai_tools.config.cache import CacheManager, get_cache_manager, cache_api_call


def test_cache_manager_basic_get_set(tmp_path):
    """Test basic setting and getting of cache values."""
    cache_dir = tmp_path / "cache"
    cache = CacheManager(cache_dir=cache_dir)

    # Key that does not exist should return None
    assert cache.get("non_existent") is None

    # Set value and get it back
    test_data = {"key": "value", "list": [1, 2, 3]}
    cache.set("test_key", test_data)
    assert cache.get("test_key") == test_data


def test_cache_manager_expiration(tmp_path):
    """Test cache expiration based on TTL."""
    cache_dir = tmp_path / "cache"
    # Set TTL of 1 second
    cache = CacheManager(cache_dir=cache_dir, default_ttl=1)

    cache.set("expire_key", "expire_value")
    # Immediate retrieval should succeed
    assert cache.get("expire_key") == "expire_value"

    # Wait for expiration
    time.sleep(1.1)
    # Retrieval after TTL should return None and clean up the file
    assert cache.get("expire_key") is None

    # Verify cache file is indeed removed
    safe_path = cache_dir / "expire_key.json"
    assert not safe_path.exists()


def test_cache_manager_custom_ttl(tmp_path):
    """Test cache retrieval with a custom TTL."""
    cache_dir = tmp_path / "cache"
    cache = CacheManager(cache_dir=cache_dir, default_ttl=10)

    cache.set("custom_key", "custom_value")

    # Accessing with 0 TTL (instant expiration) should return None
    assert cache.get("custom_key", ttl=0) is None


def test_cache_manager_malformed_file(tmp_path):
    """Test handling of malformed or corrupt cache files."""
    cache_dir = tmp_path / "cache"
    cache = CacheManager(cache_dir=cache_dir)

    key = "corrupt_key"
    cache.set(key, "good_value")

    cache_path = cache._get_cache_path(key)
    assert cache_path.exists()

    # Overwrite cache file with invalid JSON
    with open(cache_path, "w") as f:
        f.write("{invalid_json:")

    # Retrieval should gracefully handle error, return None, and clean up the file
    assert cache.get(key) is None
    assert not cache_path.exists()


def test_cache_manager_clear(tmp_path):
    """Test clearing all cache entries."""
    cache_dir = tmp_path / "cache"
    cache = CacheManager(cache_dir=cache_dir)

    cache.set("key1", "val1")
    cache.set("key2", "val2")

    # Verify files created
    files = list(cache_dir.glob("*.json"))
    assert len(files) == 2

    # Clear cache
    cache.clear()
    files = list(cache_dir.glob("*.json"))
    assert len(files) == 0


def test_cache_manager_clear_expired(tmp_path):
    """Test clearing only expired cache entries."""
    cache_dir = tmp_path / "cache"
    cache = CacheManager(cache_dir=cache_dir, default_ttl=1)

    cache.set("fresh", "value1")
    
    # Modify timestamp of 'fresh' cache manually to be in the future, or wait, we can just sleep
    cache.set("expired", "value2")
    
    # We sleep to let "expired" expire, but wait, if we sleep, both will expire.
    # To avoid sleep in tests, we can manually write a mock-expired timestamp.
    # Let's write an expired cache file manually or mock it.
    # Let's sleep for 1.1s for simplicity since default_ttl is 1s, but we only set "expired" first.
    # Let's do it cleanly:
    # Set expired
    cache.set("expired", "value2")
    time.sleep(1.1)
    # Set fresh
    cache.set("fresh", "value1")

    # Clear expired (TTL = 1s)
    removed = cache.clear_expired()
    assert removed == 1

    # 'fresh' should still exist, 'expired' should be gone
    assert cache.get("fresh") == "value1"
    assert cache.get("expired") is None


def test_global_cache_manager():
    """Test retrieving global cache manager instance."""
    cache1 = get_cache_manager()
    cache2 = get_cache_manager()
    assert cache1 is cache2


def test_cache_decorator(tmp_path):
    """Test caching decorator on API functions."""
    # Ensure global cache manager uses tmp_path to not pollute production/default cache
    import crewai_tools.config.cache as cache_module
    original_manager = cache_module._cache_manager
    
    try:
        cache_module._cache_manager = CacheManager(cache_dir=tmp_path / "decorator_cache")
        
        call_count = 0

        @cache_api_call(key="api_test", ttl=10)
        def my_api_func(param1, param2=None):
            nonlocal call_count
            call_count += 1
            return {"count": call_count, "p1": param1, "p2": param2}

        # First call: computes and caches
        res1 = my_api_func("hello", param2="world")
        assert res1["count"] == 1

        # Second call with same arguments: should return cached result, call_count remains 1
        res2 = my_api_func("hello", param2="world")
        assert res2["count"] == 1
        assert res2 == res1

        # Call with different arguments: computes again
        res3 = my_api_func("different")
        assert res3["count"] == 2

    finally:
        cache_module._cache_manager = original_manager
