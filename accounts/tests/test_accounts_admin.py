import types
import importlib
import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()

def _is_registered(model):
    return model in admin.site._registry

def _reload_accounts_admin():
    import accounts.admin as mod
    return importlib.reload(mod)

@pytest.mark.django_db
def test_admin_when_apps_present_and_unregister_succeeds(monkeypatch):
    if not _is_registered(User):
        admin.site.register(User)
    mod = _reload_accounts_admin()
    assert _is_registered(User)
    UA = mod.UserAdmin
    assert len(UA.inlines) >= 1
    ma = UA(User, admin.site)
    u = User.objects.create_user(username="a", password="x")
    assert ma.managed_tournaments_count(u) == 0
    assert ma.captain_of_teams(u) == "—"
    text = ma.permissions_summary(u)
    assert isinstance(text, str) and "staff=" in text and "groups=" in text


@pytest.mark.django_db
def test_admin_when_apps_missing_and_notregistered_branch(monkeypatch):
    if _is_registered(User):
        admin.site.unregister(User)

    dummy_models = types.SimpleNamespace()  
    monkeypatch.setitem(importlib.sys.modules, "tournaments.models", dummy_models)
    monkeypatch.setitem(importlib.sys.modules, "teams.models", dummy_models)
    monkeypatch.setitem(importlib.sys.modules, "tournaments", types.SimpleNamespace(models=dummy_models))
    monkeypatch.setitem(importlib.sys.modules, "teams", types.SimpleNamespace(models=dummy_models))

    mod = _reload_accounts_admin()

    assert _is_registered(User)
    UA = mod.UserAdmin
    assert UA.inlines == []  

    ma = UA(User, admin.site)

    u = User.objects.create_user(username="b", password="x")
    assert ma.managed_tournaments_count(u) == 0

    class _Q:
        def all(self): return []
    u2 = types.SimpleNamespace(captain_teams=_Q())
    assert ma.captain_of_teams(u2) == "—"

    assert ma.permissions_summary(types.SimpleNamespace(pk=None)) == ""

    assert ma.permissions_summary(None) == ""
    assert ma.captain_of_teams(types.SimpleNamespace()) == "—"