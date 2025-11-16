from unittest.mock import patch
import pytest
from django.test import TestCase, override_settings
from django.http import HttpResponse
from django.urls import path, reverse
from django.contrib.auth import get_user_model
from accounts import views

User = get_user_model()

LOC_TEMPLATES = {
    "accounts/profile.html": """
        {% if faceit_error %}FE:{{ faceit_error }}{% endif %}
        {% if faceit %}FACEIT_OK{% endif %}
        {% if steam %}STEAM_OK{% endif %}
        {% if used_steam_id %}USED:{{ used_steam_id }}{% endif %}
    """,
}

def _home(_r): return HttpResponse("home")

urlpatterns = [
    path("", _home, name="home"),
    path("accounts/profile/", views.profile_view, name="profile"),
]

TEMPLATES_OVERRIDE = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                ("django.template.loaders.locmem.Loader", LOC_TEMPLATES),
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]


@override_settings(ROOT_URLCONF=__name__, TEMPLATES=TEMPLATES_OVERRIDE)
class AccountsProfileAndHelpersTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="p",
            email="p@example.com",
            password="x",
        )

    def test__to_float_and__to_int(self):
        assert views._to_float("1.5") == 1.5
        assert views._to_float("bad") is None
        assert views._to_float(None) is None
        assert views._to_int("7") == 7
        assert views._to_int("x") is None
        assert views._to_int(None) is None

    def test__game_node(self):
        assert views._game_node({"games": {"cs2": {"lvl": 10}}}) == {"lvl": 10}
        assert views._game_node({"games": {"csgo": {"elo": 2000}}}) == {"elo": 2000}
        assert views._game_node({}) == {}
        assert views._game_node(None) == {}

    def test__parse_maps_all_paths_and_sort(self):
        stats_raw = {
            "segments": [
                {"type": "map", "label": "de_mirage",
                 "stats": {"Matches": "10", "Win Rate %": "66.6", "Average K/D Ratio": "1.20"}},
                {"type": "maps", "label": "cs_inferno",
                 "stats": {"Matches": "5", "K/D Ratio": "1.10"}},
                {"type": "cs2_map", "label": "", "stats": {"Matches": "0", "K/D": "2.0"}},
                {"type": "queue", "label": "de_nuke", "stats": {"Matches": "99"}},
            ]
        }
        maps = views._parse_maps(stats_raw)
        assert len(maps) == 2
        assert maps[0]["name"] == "Mirage" and maps[0]["matches"] == 10
        assert maps[1]["name"] == "Inferno" and maps[1]["matches"] == 5
        assert maps[0]["winrate"] == 66.6 and maps[0]["kd"] == 1.20
        assert maps[1]["winrate"] is None and maps[1]["kd"] == 1.10

    @patch("accounts.views.get_faceit_stats_cached")
    @patch("accounts.views.get_faceit_profile_by_steam_cached")
    @patch("accounts.views.get_steam_profile_cached")
    @patch("accounts.views.resolve_steam_input_to_steam64_cached")
    @patch("accounts.views.SteamLookupForm")
    def test_profile_post_manual_success(
        self, SteamLookupForm, resolve_steam, get_steam, get_faceit_prof, get_faceit_stats
    ):
        self.client.force_login(self.user)

        class F:
            cleaned_data = {"steam_id": "custom"}
            def __init__(self, *a, **k): pass
            def is_valid(self): return True
            def add_error(self, *a, **k): setattr(self, "_had_error", True)

        SteamLookupForm.side_effect = lambda *a, **k: F()
        resolve_steam.return_value = "76561198000000000"

        get_steam.return_value = {
            "personaname": "P",
            "avatarfull": "A",
            "profileurl": "https://steamcommunity.com/profiles/76561198000000000",
        }
        get_faceit_prof.return_value = {
            "player_id": "PID",
            "nickname": "Nick",
            "avatar": "FacePic",
            "games": {"cs2": {"skill_level": 10, "faceit_elo": 2200}},
            "_matched_game": "cs2",
        }
        get_faceit_stats.return_value = {
            "lifetime": {"Matches": "100", "Average K/D Ratio": "1.3", "Win Rate %": "52.5"},
            "segments": [
                {"type": "map", "label": "de_mirage", "stats": {"Matches": "20", "Average K/D Ratio": "1.1", "Win Rate %": "60"}}
            ],
        }

        resp = self.client.post(reverse("profile"), data={"steam_id": "whatever"})
        body = resp.content.decode()
        assert "FACEIT_OK" in body and "STEAM_OK" in body and "USED:76561198000000000" in body

    @patch("accounts.views.get_faceit_profile_by_steam_cached", return_value={"player_id": None})
    @patch("accounts.views.get_steam_profile_cached", return_value={})
    @patch("accounts.views.SteamLookupForm")
    def test_profile_post_invalid_form_fallback_to_connected(self, SteamLookupForm, _gs, _gp):
        self.client.force_login(self.user)
        self.user.steam_id = "999"; self.user.save()

        class F:
            cleaned_data = {"steam_id": None}
            def __init__(self,*a,**k): pass
            def is_valid(self): return False
            def add_error(self,*a,**k): pass

        SteamLookupForm.return_value = F()

        resp = self.client.post(reverse("profile"), data={"steam_id": "x"})
        body = resp.content.decode()
        assert "FE:⚠️ Faceit profile not found for this SteamID" in body
        assert "USED:999" in body

    @patch("accounts.views.get_faceit_profile_by_steam_cached", side_effect=Exception("boom"))
    @patch("accounts.views.get_steam_profile_cached", return_value={})
    @patch("accounts.views.SteamLookupForm")
    def test_profile_faceit_exception(self, SteamLookupForm, _get_steam, _get_faceit_prof):
        self.client.force_login(self.user)
        self.user.steam_id = "222"; self.user.save()

        class F:
            cleaned_data = {"steam_id": ""}
            def __init__(self,*a,**k): pass
            def is_valid(self): return True
            def add_error(self,*a,**k): pass

        SteamLookupForm.return_value = F()

        resp = self.client.post(reverse("profile"), data={"steam_id": ""})
        assert "FE:⚠️ Error while requesting the Faceit API. Check the API key and rate limits" in resp.content.decode()

    def test_profile_get_no_connected_shows_hint(self):
        self.client.force_login(self.user)
        self.user.steam_id = None; self.user.save()
        resp = self.client.get(reverse("profile"))
        assert "FE:Connect Steam" in resp.content.decode()

    @patch("accounts.views.get_steam_profile_cached", return_value={})
    @patch("accounts.views.resolve_steam_input_to_steam64_cached", return_value=None)
    @patch("accounts.views.SteamLookupForm")
    def test_profile_post_manual_cannot_resolve_falls_back_to_connected(
        self, SteamLookupForm, _resolve, _get_steam
    ):

        self.client.force_login(self.user)
        self.user.steam_id = "1234567890"
        self.user.save()

        holder = {}
        class F:
            cleaned_data = {"steam_id": "whatever"}
            def __init__(self, *a, **k):
                holder["inst"] = self
            def is_valid(self): return True
            def add_error(self, *a, **k): setattr(self, "_had_error", True)

        SteamLookupForm.side_effect = lambda *a, **k: F()

        resp = self.client.post(reverse("profile"), data={"steam_id": "whatever"})
        body = resp.content.decode()
        assert "USED:1234567890" in body
        assert getattr(holder.get("inst"), "_had_error", False) is True