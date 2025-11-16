import pytest
from django.core.cache import cache
from unittest.mock import patch
from accounts import services as S

@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()

def test_faceit_profile_cached_none_is_cached():
    with patch("accounts.services.get_faceit_profile_by_steam", return_value=None) as f:
        out1 = S.get_faceit_profile_by_steam_cached("x", ttl=1)
        out2 = S.get_faceit_profile_by_steam_cached("x", ttl=1)
        assert out1 is None and out2 is None
        assert f.call_count == 1 

def test_faceit_stats_cached_none_is_cached():
    with patch("accounts.services.get_faceit_stats", return_value=None) as f:
        out1 = S.get_faceit_stats_cached("pid", ttl=1)
        out2 = S.get_faceit_stats_cached("pid", ttl=1)
        assert out1 is None and out2 is None
        assert f.call_count == 1
