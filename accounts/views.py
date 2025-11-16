import re
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from .forms import SteamLookupForm, CustomUserCreationForm, ProfileEditForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib import messages
from urllib.parse import urlencode
from .services import get_faceit_profile_by_steam, get_faceit_stats, get_faceit_profile_by_steam_cached, get_faceit_stats_cached, get_steam_profile_cached, resolve_steam_input_to_steam64_cached
from .forms import SignUpForm

def _to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def _to_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None

def _game_node(prof: dict):
    games = (prof or {}).get("games", {})
    return games.get("cs2") or games.get("csgo") or {}

def register(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = SignUpForm()
    return render(request, "accounts/register.html", {"form": form})

@login_required
def profile_view(request):
    faceit = None
    faceit_error = None
    steam = None
    used_steam_id = None
    lookup_form = SteamLookupForm(request.POST or None)
    connected_id = getattr(request.user, "steam_id", None)

    raw_input = None
    if request.method == "POST" and lookup_form.is_valid():
        raw_input = (lookup_form.cleaned_data.get("steam_id") or "").strip()

    if raw_input:
        resolved = resolve_steam_input_to_steam64_cached(raw_input)
        if resolved:
            used_steam_id = resolved
        else:
            lookup_form.add_error("steam_id", "❌ Could not find a Steam profile using this input")
            used_steam_id = connected_id
    else:
        used_steam_id = connected_id

    if used_steam_id:
        sp = get_steam_profile_cached(used_steam_id)
        steam = {
            "id": used_steam_id,
            "name": (sp or {}).get("personaname"),
            "avatar": (sp or {}).get("avatarfull") or ((sp or {}).get("avatar")),
            "url": (sp or {}).get("profileurl") or f"https://steamcommunity.com/profiles/{used_steam_id}",
            "source": "manual" if (used_steam_id and used_steam_id != connected_id) else "connected",
        }

        try:
            prof = get_faceit_profile_by_steam_cached(used_steam_id)
            if prof and prof.get("player_id"):
                stats_raw = get_faceit_stats_cached(prof["player_id"]) or {}
                lifetime = stats_raw.get("lifetime", {}) or {}
                games = (prof or {}).get("games", {})
                game = games.get("cs2") or games.get("csgo") or {}

                faceit = {
                    "nickname": prof.get("nickname"),
                    "avatar": prof.get("avatar"),
                    "level": game.get("skill_level"),
                    "elo": game.get("faceit_elo"),
                    "game": prof.get("_matched_game"),
                    "lifetime": {
                        "matches": _to_int(lifetime.get("Matches")),
                        "kd_avg": _to_float(lifetime.get("Average K/D Ratio")),
                        "winrate": _to_float(lifetime.get("Win Rate %")),
                    },
                    "maps": _parse_maps(stats_raw),
                }
            else:
                faceit_error = "⚠️ Faceit profile not found for this SteamID"
        except Exception:
            faceit_error = "⚠️ Error while requesting the Faceit API. Check the API key and rate limits"
    else:
        faceit_error = "Connect Steam or enter a SteamID / link / alias manually"

    return render(request, "accounts/profile.html", {
        "faceit": faceit,
        "faceit_error": faceit_error,
        "steam": steam,
        "lookup_form": lookup_form,
        "used_steam_id": used_steam_id,
    })

@login_required
def edit_profile(request):
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("profile")
    else:
        form = ProfileEditForm(instance=request.user)

    return render(request, "accounts/profile_edit.html", {"form": form})

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def connect_steam(request):
    return_to = request.build_absolute_uri(reverse('steam_verify')) 
    realm = f"{request.scheme}://{request.get_host()}/"

    params = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.mode': 'checkid_setup',
        'openid.return_to': return_to,
        'openid.realm': realm,
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
    }
    url = 'https://steamcommunity.com/openid/login?' + urlencode(params)
    return redirect(url)

@login_required
def steam_verify(request):
    claimed_id = request.GET.get("openid.claimed_id")
    if claimed_id:
        m = re.search(r'/id/(\d+)$', claimed_id)
        if m:
            steam_id = m.group(1)
            request.user.steam_id = steam_id
            request.user.save(update_fields=["steam_id"])
            return redirect("profile")

    messages.error(request, "Failed to verify Steam account")
    return redirect("profile")

@login_required
def steam_disconnect(request):
    request.user.steam_id = None
    request.user.save(update_fields=["steam_id"])
    return redirect("profile")

@login_required
def faceit_stats_view(request):
    steam_id = request.user.steam_id
    if not steam_id:
        return render(request, "accounts/faceit_stats.html", {"error": "Connect Steam first"})

    profile = get_faceit_profile_by_steam(steam_id)
    if not profile:
        return render(request, "accounts/faceit_stats.html", {"error": "Faceit profile not found"})

    stats = get_faceit_stats(profile["player_id"])
    return render(request, "accounts/faceit_stats.html", {
        "profile": profile,
        "stats": stats,
    })

def _parse_maps(stats_raw):
    segs = (stats_raw or {}).get("segments") or []
    maps = []
    for seg in segs:
        t = (seg.get("type") or "").lower()
        if t not in ("map", "maps", "csgo_map", "cs2_map"):
            continue

        label = seg.get("label") or seg.get("mode") or seg.get("map") or ""
        name = label.replace("de_", "").replace("cs_", "").strip().capitalize() or "—"

        st = seg.get("stats") or {}
        matches = _to_int(st.get("Matches"))
        winrate = _to_float(st.get("Win Rate %"))
        kd = (_to_float(st.get("Average K/D Ratio"))
              or _to_float(st.get("K/D Ratio"))
              or _to_float(st.get("K/D")))

        if matches:
            maps.append({
                "name": name,
                "matches": matches,
                "winrate": winrate,
                "kd": kd,
            })

    maps.sort(key=lambda m: m["matches"], reverse=True)
    return maps[:12]