import os
import time
from nylb.collectors.cache import get_cached, put_cache


def test_cache_put_get_roundtrip(tmp_path):
    url = "https://www.kurly.com/goods/1"
    assert get_cached(url, ttl_days=7, base_dir=tmp_path) is None
    put_cache(url, "<html>hi</html>", base_dir=tmp_path)
    assert get_cached(url, ttl_days=7, base_dir=tmp_path) == "<html>hi</html>"


def test_cache_ttl_expiry(tmp_path):
    url = "https://www.kurly.com/goods/2"
    put_cache(url, "old", base_dir=tmp_path)
    f = next(tmp_path.glob("*.html"))
    old = time.time() - 10 * 86400
    os.utime(f, (old, old))
    assert get_cached(url, ttl_days=7, base_dir=tmp_path) is None
