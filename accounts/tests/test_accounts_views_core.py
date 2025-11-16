# accounts/tests/test_views_core.py
from unittest.mock import MagicMock, patch
import pytest
from django.test import TestCase, override_settings
from django.http import HttpResponse
from django.urls import path, reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages

from accounts import views

User = get_user_model()

LOC_TEMPLATES = {
    "accounts/register.html": "REGISTER {{ form }}",
    "accounts/login.html": "LOGIN {{ form }}",
    "accounts/profile.html": """
        {% if faceit_error %}FE:{{ faceit_error }}{% endif %}
        {% if faceit %}FACEIT_OK{% endif %}
        {% if steam %}STEAM_OK{% endif %}
        {% if used_steam_id %}USED:{{ used_steam_id }}{% endif %}
    """,
    "accounts/faceit_stats.html": """
        {% if error %}ERR:{{ error }}{% endif %}
        {% if profile %}PF_OK{% endif %}
    """,
    "accounts/profile_edit.html": "EDIT {{ form }}",
}

def _dummy_home(_req):  
    return HttpResponse("home")

urlpatterns = [
    path("", _dummy_home, name="home"),
    path("accounts/register/", views.register_view, name="register"),
    path("accounts/register2/", views.register, name="register2"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),
    path("accounts/profile/", views.profile_view, name="profile"),
    path("accounts/profile/edit/", views.edit_profile, name="edit_profile"),
    path("accounts/steam/connect/", views.connect_steam, name="connect_steam"),
    path("accounts/steam/verify/", views.steam_verify, name="steam_verify"),
    path("accounts/steam/disconnect/", views.steam_disconnect, name="steam_disconnect"),
    path("accounts/faceit/", views.faceit_stats_view, name="faceit_stats"),
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
class AccountsViewsCoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u",
            email="u@example.com",
            password="p@ssw0rd",
        )

    @patch("accounts.views.CustomUserCreationForm")
    def test_register_view_post_valid(self, CustomUserCreationForm):
        form = MagicMock()
        form.is_valid.return_value = True
        form.save.return_value = self.user
        CustomUserCreationForm.return_value = form

        resp = self.client.post(reverse("register"), data={"any": "x"})
        assert resp.status_code == 302
        assert resp.url == reverse("home")

    @patch("accounts.views.CustomUserCreationForm")
    def test_register_view_get_and_post_invalid(self, CustomUserCreationForm):
        form = MagicMock()
        form.is_valid.return_value = False
        CustomUserCreationForm.return_value = form

        resp = self.client.get(reverse("register"))
        assert resp.status_code == 200

        resp = self.client.post(reverse("register"), data={"any": "x"})
        assert resp.status_code == 200

    @patch("accounts.views.SignUpForm")
    def test_register_post_valid(self, SignUpForm):
        form = MagicMock()
        form.is_valid.return_value = True
        form.save.return_value = self.user
        SignUpForm.return_value = form

        resp = self.client.post(reverse("register2"), data={"x": "y"})
        assert resp.status_code == 302
        assert resp.url == reverse("home")

    @patch("accounts.views.SignUpForm")
    def test_register_get_and_post_invalid(self, SignUpForm):
        form = MagicMock()
        form.is_valid.return_value = False
        SignUpForm.return_value = form

        resp = self.client.get(reverse("register2"))
        assert resp.status_code == 200

        resp = self.client.post(reverse("register2"), data={"x": "y"})
        assert resp.status_code == 200

    @patch("accounts.views.AuthenticationForm")
    def test_login_valid(self, AuthenticationForm):
        form = MagicMock()
        form.is_valid.return_value = True
        form.get_user.return_value = self.user
        AuthenticationForm.return_value = form

        resp = self.client.post(reverse("login"), data={"u": "u", "p": "p"})
        assert resp.status_code == 302
        assert resp.url == reverse("home")

    @patch("accounts.views.AuthenticationForm")
    def test_login_invalid(self, AuthenticationForm):
        form = MagicMock()
        form.is_valid.return_value = False
        AuthenticationForm.return_value = form

        resp = self.client.get(reverse("login"))
        assert resp.status_code == 200

        resp = self.client.post(reverse("login"), data={"u": "u", "p": "p"})
        assert resp.status_code == 200

    def test_logout(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("logout"))
        assert resp.status_code == 302
        assert resp.url == reverse("login")

    @patch("accounts.views.ProfileEditForm")
    def test_edit_profile_get_post_valid_and_invalid(self, ProfileEditForm):
        self.client.force_login(self.user)

        ProfileEditForm.return_value = MagicMock()
        resp = self.client.get(reverse("edit_profile"))
        assert resp.status_code == 200

        form_valid = MagicMock()
        form_valid.is_valid.return_value = True
        ProfileEditForm.return_value = form_valid
        resp = self.client.post(reverse("edit_profile"), data={"bio": "x"})
        assert resp.status_code == 302 and resp.url == reverse("profile")

        form_invalid = MagicMock()
        form_invalid.is_valid.return_value = False
        ProfileEditForm.return_value = form_invalid
        resp = self.client.post(reverse("edit_profile"), data={"bio": "x"})
        assert resp.status_code == 200

    def test_connect_steam_builds_openid_url(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("connect_steam"))
        assert resp.status_code == 302
        assert resp.url.startswith("https://steamcommunity.com/openid/login?")
        assert "openid.mode=checkid_setup" in resp.url
        assert "openid.return_to=" in resp.url
        assert "openid.realm=" in resp.url

    def test_steam_verify_success_and_failure(self):
        self.client.force_login(self.user)
        ok = reverse("steam_verify") + "?openid.claimed_id=https://steamcommunity.com/openid/id/76561198000000000"
        resp = self.client.get(ok)
        assert resp.status_code == 302 and resp.url == reverse("profile")
        self.user.refresh_from_db()
        assert self.user.steam_id == "76561198000000000"

        bad = reverse("steam_verify") + "?openid.claimed_id=https://steamcommunity.com/openid/id/NaN"
        resp = self.client.get(bad)
        assert resp.status_code == 302 and resp.url == reverse("profile")
        storage = list(get_messages(resp.wsgi_request))

    def test_steam_disconnect(self):
        self.client.force_login(self.user)
        self.user.steam_id = "123"; self.user.save(update_fields=["steam_id"])
        resp = self.client.get(reverse("steam_disconnect"))
        assert resp.status_code == 302 and resp.url == reverse("profile")
        self.user.refresh_from_db()
        assert self.user.steam_id is None

    # -------- faceit_stats_view: все ветки
    def test_faceit_stats_requires_steam(self):
        self.client.force_login(self.user)
        self.user.steam_id = None; self.user.save()
        resp = self.client.get(reverse("faceit_stats"))
        body = resp.content.decode()
        assert "Connect Steam first" in body or "ERR:Connect Steam first" in body

    @patch("accounts.views.get_faceit_profile_by_steam")
    def test_faceit_stats_profile_not_found(self, get_faceit_profile_by_steam):
        self.client.force_login(self.user)
        self.user.steam_id = "7656"; self.user.save()
        get_faceit_profile_by_steam.return_value = None
        resp = self.client.get(reverse("faceit_stats"))
        assert "Faceit profile not found" in resp.content.decode()

    @patch("accounts.views.get_faceit_stats")
    @patch("accounts.views.get_faceit_profile_by_steam")
    def test_faceit_stats_ok(self, get_faceit_profile_by_steam, get_faceit_stats):
        self.client.force_login(self.user)
        self.user.steam_id = "7656"; self.user.save()
        get_faceit_profile_by_steam.return_value = {"player_id": "pid", "nickname": "nick"}
        get_faceit_stats.return_value = {"lifetime": {"Matches": "1"}}
        resp = self.client.get(reverse("faceit_stats"))
        assert "PF_OK" in resp.content.decode()

    def test_steam_verify_no_params_triggers_error_branch(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("steam_verify"))
        assert resp.status_code == 302 and resp.url == reverse("profile")
        from django.contrib.messages import get_messages
        storage = list(get_messages(resp.wsgi_request))
        assert storage is not None