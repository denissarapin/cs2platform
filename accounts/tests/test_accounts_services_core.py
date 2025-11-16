import json
import pytest
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from django.test import override_settings
import requests
from accounts import services as S

@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()

class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self._text = json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if 400 <= self.status_code:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err

@patch("accounts.services.requests.get")
def test__get_ok(req_get):
    req_get.return_value = _Resp(200, {"hello": "world"})
    out = S._get("https://x/api", params={"a": 1})
    assert out == {"hello": "world"}
    req_get.assert_called_once()

@patch("accounts.services.requests.get")
def test__get_404_returns_none(req_get):
    req_get.return_value = _Resp(404, {"detail": "not found"})
    out = S._get("https://x/api")
    assert out is None

@patch("accounts.services.requests.get")
def test__get_500_raises(req_get):
    req_get.return_value = _Resp(500, {"err": "boom"})
    with pytest.raises(requests.HTTPError):
        S._get("https://x/api")
    req_get.assert_called_once()

@patch("accounts.services._get")
def test_get_faceit_profile_by_steam_hits_cs2_first(_get):
    _get.return_value = {"player_id": "PID"}
    out = S.get_faceit_profile_by_steam("7656")
    assert out["player_id"] == "PID"
    assert out["_matched_game"] == "cs2"
    _get.assert_called_once()

@patch("accounts.services._get")
def test_get_faceit_profile_by_steam_cs2_404_then_csgo_ok(_get):
    e = requests.HTTPError("404")
    e.response = MagicMock(status_code=404)
    _get.side_effect = [e, {"player_id": "X"}]

    out = S.get_faceit_profile_by_steam("7656")
    assert out and out["player_id"] == "X"
    assert out["_matched_game"] == "csgo"


@patch("accounts.services._get")
def test_get_faceit_profile_by_steam_cs2_http_error_non404_then_continue(_get, caplog):
    e = requests.HTTPError("500")
    e.response = MagicMock(status_code=500)
    _get.side_effect = [e, None]
    out = S.get_faceit_profile_by_steam("7656")
    assert out is None 

@patch("accounts.services._get")
def test_get_faceit_profile_by_steam_generic_exception_then_none(_get):
    _get.side_effect = [Exception("boom"), None]
    out = S.get_faceit_profile_by_steam("7656")
    assert out is None

@patch("accounts.services._get")
def test_get_faceit_stats_cs2_ok(_get):
    _get.return_value = {"k": "v"}
    out = S.get_faceit_stats("PID")
    assert out == {"k": "v"}
    _get.assert_called_once_with(f"{S.BASE}/players/PID/stats/cs2")

@patch("accounts.services._get")
def test_get_faceit_stats_cs2_http_error_fallback_csgo(_get):
    e = requests.HTTPError("oops")
    e.response = MagicMock(status_code=500)
    _get.side_effect = [e, {"ok": True}]
    out = S.get_faceit_stats("PID")
    assert out == {"ok": True}
    assert _get.call_count == 2
    assert _get.call_args_list[-1][0][0] == f"{S.BASE}/players/PID/stats/csgo"

@patch("accounts.services._get")
def test_get_faceit_stats_cs2_none_fallback_csgo(_get):
    _get.side_effect = [None, {"csgo": 1}]
    out = S.get_faceit_stats("PID")
    assert out == {"csgo": 1}

@patch("accounts.services.get_faceit_profile_by_steam", return_value={"player_id": "P"})
def test_get_faceit_profile_by_steam_cached_miss_then_hit(func):
    cache.clear()
    key = "765"
    out = S.get_faceit_profile_by_steam_cached(key, ttl=1)
    assert out == {"player_id": "P"}
    out2 = S.get_faceit_profile_by_steam_cached(key, ttl=1)
    assert out2 == {"player_id": "P"}
    assert func.call_count == 1

@patch("accounts.services.get_faceit_stats", return_value={"stats": 1})
def test_get_faceit_stats_cached_miss_then_hit(func):
    cache.clear()
    out = S.get_faceit_stats_cached("PID", ttl=1)
    assert out == {"stats": 1}
    out2 = S.get_faceit_stats_cached("PID", ttl=1)
    assert out2 == {"stats": 1}
    assert func.call_count == 1

def _mk_players(payload):
    return {"response": {"players": payload}}

@override_settings(STEAM_WEB_API_KEY="")
@patch("accounts.services.requests.get")
def test_get_steam_profile_no_key_returns_none(req_get):
    assert S.get_steam_profile("7656") is None
    req_get.assert_not_called()

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.requests.get")
def test_get_steam_profile_ok_and_empty(req_get):
    req_get.return_value = _Resp(200, _mk_players([{"id": 1}]))
    out = S.get_steam_profile("7656")
    assert out == {"id": 1}
    req_get.return_value = _Resp(200, _mk_players([]))
    out2 = S.get_steam_profile("7656")
    assert out2 is None
    assert req_get.call_count == 2

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.requests.get")
def test_get_steam_profile_http_error(req_get):
    req_get.return_value = _Resp(500, {})
    with pytest.raises(requests.HTTPError):
        S.get_steam_profile("7656")

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.get_steam_profile", side_effect=[{"x": 1}, Exception("boom")])
def test_get_steam_profile_cached_miss_then_hit_and_exception_swallowed(func):
    cache.clear()
    out1 = S.get_steam_profile_cached("765", ttl=1)
    assert out1 == {"x": 1}
    out2 = S.get_steam_profile_cached("765", ttl=1)
    assert out2 == {"x": 1}
    out3 = S.get_steam_profile_cached("999", ttl=1)
    assert out3 is None
    assert func.call_count == 2

def test__parse_steam_input_variants():
    f = S._parse_steam_input
    assert f("") == (None, None)
    assert f("   ") == (None, None)
    assert f("https://steamcommunity.com/profiles/765") == ("steamid64", "765")
    assert f("steamcommunity.com/profiles/987") == ("steamid64", "987")
    assert f("https://steamcommunity.com/id/somealias") == ("vanity", "somealias")
    assert f("steamcommunity.com/id/alias") == ("vanity", "alias")
    assert f("123456") == ("steamid64", "123456")
    assert f("nickname") == ("vanity", "nickname")

@override_settings(STEAM_WEB_API_KEY="")
@patch("accounts.services.requests.get")
def test_resolve_vanity_to_steam64_no_key(req_get):
    assert S.resolve_vanity_to_steam64("alias") is None
    req_get.assert_not_called()

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.requests.get")
def test_resolve_vanity_to_steam64_success(req_get):
    req_get.return_value = _Resp(200, {"response": {"success": 1, "steamid": "765"}})
    out = S.resolve_vanity_to_steam64("alias")
    assert out == "765"
    req_get.assert_called_once()

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.requests.get")
def test_resolve_vanity_to_steam64_failure(req_get):
    req_get.return_value = _Resp(200, {"response": {"success": 42}})
    out = S.resolve_vanity_to_steam64("alias")
    assert out is None

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.requests.get")
def test_resolve_vanity_to_steam64_http_error(req_get):
    req_get.return_value = _Resp(500, {})
    with pytest.raises(requests.HTTPError):
        S.resolve_vanity_to_steam64("alias")

@override_settings(STEAM_WEB_API_KEY="KEY")
def test_resolve_steam_input_to_steam64_direct_number():
    assert S.resolve_steam_input_to_steam64("76561198000000000") == "76561198000000000"

@override_settings(STEAM_WEB_API_KEY="KEY")
def test_resolve_steam_input_to_steam64_profiles_url():
    out = S.resolve_steam_input_to_steam64("https://steamcommunity.com/profiles/7656119801")
    assert out == "7656119801"

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.resolve_vanity_to_steam64", return_value="777")
def test_resolve_steam_input_to_steam64_id_url(resolve):
    out = S.resolve_steam_input_to_steam64("https://steamcommunity.com/id/somealias")
    assert out == "777"
    resolve.assert_called_once_with("somealias")

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.resolve_vanity_to_steam64", return_value=None)
def test_resolve_steam_input_to_steam64_alias(resolve):
    out = S.resolve_steam_input_to_steam64("somealias")
    assert out is None
    resolve.assert_called_once_with("somealias")

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.resolve_vanity_to_steam64", side_effect=Exception("boom"))
def test_resolve_steam_input_to_steam64_cached_handles_exception_and_caches_none(resolve):
    cache.clear()
    out1 = S.resolve_steam_input_to_steam64_cached("alias", ttl=60)
    out2 = S.resolve_steam_input_to_steam64_cached("alias", ttl=60)
    assert out1 is None and out2 is None
    assert resolve.call_count == 1  # из-за кэша

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.resolve_steam_input_to_steam64", return_value="765")
def test_resolve_steam_input_to_steam64_cached_hit(resolve):
    cache.clear()
    out1 = S.resolve_steam_input_to_steam64_cached("alias", ttl=60)
    out2 = S.resolve_steam_input_to_steam64_cached("alias", ttl=60)
    assert out1 == "765" and out2 == "765"
    assert resolve.call_count == 1

def test_resolve_steam_input_to_steam64_empty_returns_none():
    assert S.resolve_steam_input_to_steam64("") is None
    assert S.resolve_steam_input_to_steam64("   ") is None


@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.resolve_vanity_to_steam64", return_value="7654321")
def test_resolve_steam_input_to_steam64_scheme_less_id_url(resolve):
    out = S.resolve_steam_input_to_steam64("steamcommunity.com/id/somealias")
    assert out == "7654321"
    resolve.assert_called_once_with("somealias")


@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.urlparse", side_effect=Exception("boom"))
@patch("accounts.services.resolve_vanity_to_steam64", return_value=None)
def test_resolve_steam_input_to_steam64_handles_urlparse_exception(resolve, _urlparse):
    out = S.resolve_steam_input_to_steam64("somealias")
    assert out is None
    resolve.assert_called_once_with("somealias")

@override_settings(STEAM_WEB_API_KEY="KEY")
@patch("accounts.services.resolve_vanity_to_steam64", return_value=None)
def test_resolve_steam_input_to_steam64_id_without_vanity_falls_back(resolve):
    out = S.resolve_steam_input_to_steam64("https://steamcommunity.com/id/")
    assert out is None
    resolve.assert_called_once_with("https://steamcommunity.com/id/")