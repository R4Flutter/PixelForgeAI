from __future__ import annotations

from infrastructure.cache.disk_cache import DiskCache


class TestDiskCache:
    def test_get_missing_key(self) -> None:
        cache = DiskCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_set_and_get(self) -> None:
        cache = DiskCache()
        import tempfile
        tempdir = tempfile.mkdtemp()
        cache._cache_dir = tempdir

        key = "test_key"
        value = b"test_value"
        path = cache.set(key, value)

        if path:
            retrieved = cache.get(key)
            assert retrieved is not None
