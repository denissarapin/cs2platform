import logging
import requests
from django.conf import settings
from django.core.cache import cache
from urllib.parse import urlparse
import re
import hashlib
log = logging.getLogger(__name__)

BASE = "https://open.faceit.com/data/v4"
HEADERS = {"Authorization": f"Bearer {settings.FACEIT_API_KEY}"}

def _get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=8)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def get_faceit_profile_by_steam(steam_id64: str):
    for game in ("cs2", "csgo"):
        try:
            data = _get(f"{BASE}/players", params={"game": game, "game_player_id": steam_id64})
            if data and data.get("player_id"):
                data["_matched_game"] = game
                return data
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                continue
            else:
                log.warning(f"Faceit lookup failed for {steam_id64} ({game}): {e}")
                continue
        except Exception:
            log.exception("Faceit lookup error")
    return None

def get_faceit_stats(player_id: str):

    try:
        data = _get(f"{BASE}/players/{player_id}/stats/cs2")
        if data:
            return data
    except requests.HTTPError:
        pass
    return _get(f"{BASE}/players/{player_id}/stats/csgo")

def get_faceit_profile_by_steam_cached(steam_id64: str, ttl=300):
    key = f"faceit:profile:{steam_id64}"
    _MISSING = object()
    cached = cache.get(key, _MISSING)
    if cached is not _MISSING:
        return cached
    data = get_faceit_profile_by_steam(steam_id64)
    cache.set(key, data, ttl)
    return data

def get_faceit_stats_cached(player_id: str, ttl=300):
    key = f"faceit:stats:{player_id}"
    _MISSING = object()
    cached = cache.get(key, _MISSING)
    if cached is not _MISSING:
        return cached
    data = get_faceit_stats(player_id)
    cache.set(key, data, ttl)
    return data

def get_steam_profile(steam_id64: str):
    key = settings.STEAM_WEB_API_KEY
    if not key:
        return None
    url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    r = requests.get(url, params={"key": key, "steamids": steam_id64}, timeout=8)
    r.raise_for_status()
    players = (r.json() or {}).get("response", {}).get("players", [])
    return players[0] if players else None

def get_steam_profile_cached(steam_id64: str, ttl=600):
    cache_key = f"steam:profile:{steam_id64}"
    data = cache.get(cache_key)
    if data is None:
        try:
            data = get_steam_profile(steam_id64)
        except Exception:
            data = None
        cache.set(cache_key, data, ttl)
    return data

STEAM_PROFILES_RE = re.compile(r"(?:https?://)?steamcommunity\.com/profiles/(\d+)", re.I)
STEAM_ID_RE       = re.compile(r"(?:https?://)?steamcommunity\.com/id/([^/?#]+)", re.I)

def _parse_steam_input(s: str):
    s = (s or "").strip()
    if not s:
        return None, None
    m = STEAM_PROFILES_RE.search(s)
    if m:
        return "steamid64", m.group(1)
    m = STEAM_ID_RE.search(s)
    if m:
        return "vanity", m.group(1)
    if s.isdigit():
        return "steamid64", s
    return "vanity", s 

def resolve_vanity_to_steam64(vanity: str) -> str | None:
    key = settings.STEAM_WEB_API_KEY
    if not key:
        return None
    url = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
    r = requests.get(url, params={"key": key, "vanityurl": vanity, "url_type": 1}, timeout=8)
    r.raise_for_status()
    resp = (r.json() or {}).get("response", {})
    if resp.get("success") == 1 and resp.get("steamid"):
        return resp["steamid"]
    return None

def resolve_steam_input_to_steam64(raw: str) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None

    if s.isdigit() and len(s) >= 16:
        return s

    parsed = None
    try:
        parsed = urlparse(s if "://" in s else f"https://{s}")
    except Exception:
        parsed = None 

    if parsed is not None:
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").strip("/")
        if "steamcommunity.com" in host and path:
            parts = path.split("/")
            if parts[0] == "profiles" and len(parts) > 1 and parts[1].isdigit():
                return parts[1]
            if parts[0] == "id" and len(parts) > 1:
                vanity = parts[1]
                return resolve_vanity_to_steam64(vanity)
    return resolve_vanity_to_steam64(s)
    
def resolve_steam_input_to_steam64_cached(raw: str, ttl=600) -> str | None:
    key_base = (raw or '').strip().lower().encode()
    key = f"steam:resolve:{hashlib.sha1(key_base).hexdigest()}"

    _MISSING = object()
    cached = cache.get(key, _MISSING)
    if cached is not _MISSING:
        return cached

    try:
        steam64 = resolve_steam_input_to_steam64(raw)
    except Exception:
        steam64 = None

    cache.set(key, steam64, ttl)
    return steam64