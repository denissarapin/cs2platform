import types
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import override_settings
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.template.loader import render_to_string
from tournaments.models import Tournament, TournamentTeam, Match, MAP_POOL
from teams.models import Team
from tournaments import views as V
from unittest import mock

User = get_user_model()

LOC_TPL = {
    "tournaments/tournament_form.html": "FORM {{ title }}",
    "tournaments/tournament_list.html": "LIST {{ tournaments|length }}",
    "tournaments/overview.html": "OVERVIEW {{ tournament.id }} {{ registered_count }} {{ registered_pct }} {% if joined_team %}JOINED:{{ joined_team.id }}{% endif %} CAN_JOIN={{ can_join }}",
    "tournaments/bracket.html": "{% for r in rounds %}[{{ r.num }}|{{ r.label }}]{% endfor %}",
    "tournaments/matches.html": "MATCHES {{ matches|length }}",
    "tournaments/teams.html": "TEAMS {{ participants|length }}",
    "tournaments/results.html": "RESULTS {{ matches|length }}",
    "tournaments/settings.html": "SETTINGS {{ form|default:'-' }}",
    "tournaments/_match.html": "<div>MATCH {{ match.id }}</div>",
    "tournaments/match_detail.html": "MATCH_DETAIL {{ final_map.0|default:'-' }} {{ final_map.1|default:'-' }}",
    "tournaments/match_detail_inner.html": "INNER {{ final_map.0|default:'-' }} {{ final_map.1|default:'-' }}",
}

TEMPLATES_OVERRIDE = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": False,
    "OPTIONS": {
        "loaders": [("django.template.loaders.locmem.Loader", LOC_TPL)],
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]

pytestmark = pytest.mark.django_db


def _mk_staff():
    return User.objects.create_user("staff", password="x", is_staff=True, email="s@s.s")


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_create_get_and_post_valid(monkeypatch):
    staff = _mk_staff()

    class F:
        def __init__(self, *a, **k): self.cleaned = True
        def is_valid(self): return True
        def save(self, commit=False):
            t = Tournament.objects.create(name="T", start_date=timezone.now())
            return t
    monkeypatch.setattr(V, "TournamentForm", F)


    from django.test import Client
    c = Client()
    c.force_login(staff)

    r = c.get(reverse("tournaments:create"))
    assert r.status_code == 200
    assert "FORM Create tournament" in r.content.decode()

    r = c.post(reverse("tournaments:create"), data={"name": "X"})
    assert r.status_code == 302
    assert "/tournaments/" in r["Location"]


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_create_post_invalid(monkeypatch):
    staff = _mk_staff()
    class F:
        def __init__(self, *a, **k): pass
        def is_valid(self): return False
    monkeypatch.setattr(V, "TournamentForm", F)

    from django.test import Client
    c = Client(); c.force_login(staff)
    r = c.post(reverse("tournaments:create"), data={"name": ""})
    assert r.status_code == 200
    assert "FORM Create tournament" in r.content.decode()


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_list_and_overview_anonymous_and_joined(make_team):
    t = Tournament.objects.create(name="L1", start_date=timezone.now(), max_teams=8)
    t2 = Tournament.objects.create(name="L2", start_date=timezone.now(), max_teams=8)

    from django.test import Client
    c = Client()
    r = c.get(reverse("tournaments:list"))
    assert r.status_code == 200
    assert "LIST 2" in r.content.decode()

    r2 = c.get(reverse("tournaments:overview", args=[t.id]))
    body = r2.content.decode()
    assert "OVERVIEW" in body and "CAN_JOIN=False" in body

    team = make_team("A")
    r3 = c.get(reverse("tournaments:overview", args=[t.id]) + f"?joined={team.id}")
    assert f"JOINED:{team.id}" in r3.content.decode()


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_hero_ctx_can_join_and_already_registered(make_team):
    u = User.objects.create_user("cap", password="x", email="c@c.c")
    team = make_team("CaptainTeam", captain=u)
    t = Tournament.objects.create(
        name="OV", start_date=timezone.now(), max_teams=2,
        status="upcoming", registration_open=True
    )

    from django.test import Client
    c = Client(); c.force_login(u)

    r = c.get(reverse("tournaments:overview", args=[t.id]))
    assert "CAN_JOIN=True" in r.content.decode()

    TournamentTeam.objects.create(tournament=t, team=team)
    r2 = c.get(reverse("tournaments:overview", args=[t.id]))
    assert "CAN_JOIN=False" in r2.content.decode()


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_bracket_round_labels(make_team, monkeypatch):
    t = Tournament.objects.create(name="B", start_date=timezone.now())
    a = make_team("A"); b = make_team("B")
    for rnd in (1, 2, 3, 4):
        Match.objects.create(tournament=t, team_a=a, team_b=b, round=rnd)

    captured = {}
    def fake_render(request, template_name, ctx):
        captured["ctx"] = ctx
        return HttpResponse("OK")
    monkeypatch.setattr(V, "render", fake_render)

    from django.test import Client
    u = User.objects.create_user("u", password="x")
    c = Client(); c.force_login(u)

    r = c.get(reverse("tournaments:bracket", args=[t.id]))
    assert r.status_code == 200
    ctx = captured["ctx"]
    assert ctx["tournament"].id == t.id
    rounds = ctx["rounds"]

    labels = [x["label"] for x in rounds]
    nums   = [x["num"] for x in rounds]

    assert "Final" in labels
    assert "Semi finals" in labels
    assert "Quarter finals" in labels
    assert "Round of 16" in labels
    assert 4 in nums


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_toggle_registration_ok_and_wrong_status(make_team):
    staff = _mk_staff()
    t = Tournament.objects.create(name="TGL", start_date=timezone.now(), registration_open=True)
    from django.test import Client
    c = Client(); c.force_login(staff)

    r = c.get(reverse("tournaments:toggle_registration", args=[t.id]))
    assert r.status_code == 302
    t.refresh_from_db()
    assert t.registration_open is False

    t.status = "running"; t.save(update_fields=["status"])
    r2 = c.get(reverse("tournaments:toggle_registration", args=[t.id]))
    assert r2.status_code == 302


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE, TOURNAMENT_MIN_TEAMS=3)
def test_start_tournament_not_enough_and_enough(make_team, monkeypatch):
    staff = _mk_staff()
    t = Tournament.objects.create(name="ST", start_date=timezone.now(), max_teams=8)
    from django.test import Client
    c = Client(); c.force_login(staff)

    r = c.post(reverse("tournaments:start", args=[t.id]))
    assert r.status_code == 200
    assert "SETTINGS" in r.content.decode()

    a = make_team("A"); b = make_team("B"); cteam = make_team("C")
    TournamentTeam.objects.create(tournament=t, team=a)
    TournamentTeam.objects.create(tournament=t, team=b)
    TournamentTeam.objects.create(tournament=t, team=cteam)

    gen_called = {"v": 0}; upd_called = {"v": 0}
    monkeypatch.setattr(V, "generate_full_bracket", lambda _t: gen_called.__setitem__("v", 1))
    monkeypatch.setattr(V, "update_bracket_progression", lambda _t: upd_called.__setitem__("v", 1))

    r2 = c.post(reverse("tournaments:start", args=[t.id]))
    assert r2.status_code == 302 and "/bracket" in r2["Location"]
    t.refresh_from_db()
    assert t.status == "running" and t.registration_open is False
    assert gen_called["v"] == 1 and upd_called["v"] == 1

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_start_tournament_early_redirect_when_already_running():
    staff = _mk_staff()
    from django.test import Client
    c = Client(); c.force_login(staff)

    t = Tournament.objects.create(name="ST", start_date=timezone.now(), status="running")
    r = c.post(reverse("tournaments:start", args=[t.id]))
    assert r.status_code == 302 and reverse("tournaments:bracket", args=[t.id]) in r["Location"]


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_settings_forbidden_and_post_paths(make_team, monkeypatch):
    u = User.objects.create_user("u", password="x")
    t = Tournament.objects.create(name="SET", start_date=timezone.now())
    from django.test import Client
    c = Client(); c.force_login(u)
    r = c.get(reverse("tournaments:settings", args=[t.id]))
    assert r.status_code == 403
    u.is_staff = True; u.save()
    class DummyForm:
        _bo_field_name = "bo"
        def __init__(self, data=None, instance=None): self.cleaned_data = {"bo": "3"}; self._valid = True
        def is_valid(self): return self._valid
        def save(self, commit=False): return instance
    instance = t
    monkeypatch.setattr(V, "TournamentSettingsForm", DummyForm)

    data = {"status": "upcoming"}
    r2 = c.post(reverse("tournaments:settings", args=[t.id]), data=data)
    assert r2.status_code == 302

    class BadForm(DummyForm):
        def __init__(self, *a, **k): self._valid = False
        def save(self, *a, **k): raise AssertionError("should not save")
    monkeypatch.setattr(V, "TournamentSettingsForm", BadForm)
    r3 = c.post(reverse("tournaments:settings", args=[t.id]), data={})
    assert r3.status_code == 302

    class PlainForm(DummyForm):
        def __init__(self, instance=None): self.initial = {}
        def is_valid(self): return True
    monkeypatch.setattr(V, "TournamentSettingsForm", PlainForm)
    t.start_date = timezone.now()
    t.end_date = t.start_date + timedelta(hours=2)
    t.save()
    r4 = c.get(reverse("tournaments:settings", args=[t.id]))
    assert r4.status_code == 200
    assert "SETTINGS" in r4.content.decode()

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_settings_bool_autofill_and_bo_field(monkeypatch):
    staff = _mk_staff()
    from django.test import Client
    c = Client(); c.force_login(staff)
    t = Tournament.objects.create(
        name="SET2",
        start_date=timezone.now(),
        registration_open=True,
        max_teams=4,
    )

    captured = {"seen": {}}
    class FormSpy:
        _bo_field_name = "max_teams"
        def __init__(self, data=None, instance=None):
            captured["seen"] = dict(data or {})
            self.cleaned_data = {"max_teams": "8"}
        def is_valid(self): return True
        def save(self, commit=False): return instance

    instance = t
    monkeypatch.setattr(V, "TournamentSettingsForm", FormSpy)
    r = c.post(reverse("tournaments:settings", args=[t.id]), data={"status": "upcoming"})
    assert r.status_code == 302
    val = captured["seen"].get("registration_open")
    if isinstance(val, list):
        val = val[0]
    assert val == "on"

    t.refresh_from_db()
    assert t.max_teams == 8

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_settings_get_initial_datetime_filled(monkeypatch):
    staff = _mk_staff()
    from django.test import Client
    c = Client(); c.force_login(staff)

    t = Tournament.objects.create(name="SET3", start_date=timezone.now(), end_date=timezone.now()+timedelta(hours=1))

    class PlainForm:
        def __init__(self, instance=None):
            self.initial = {}
        def is_valid(self): return True

    captured = {}
    monkeypatch.setattr(V, "TournamentSettingsForm", PlainForm)
    def fake_render(request, tpl, ctx):
        captured["form"] = ctx["form"]
        return HttpResponse("OK")
    monkeypatch.setattr(V, "render", fake_render)

    r = c.get(reverse("tournaments:settings", args=[t.id]))
    assert r.status_code == 200
    form = captured["form"]
    assert "start_date" in form.initial and "end_date" in form.initial
    assert "T" in form.initial["start_date"]

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_settings_bo_field_false_branch(monkeypatch):
    staff = _mk_staff()
    from django.test import Client
    c = Client(); c.force_login(staff)
    t = Tournament.objects.create(name="SET-BO-FALSE", start_date=timezone.now(), max_teams=4)
    saved = {"called": False}
    class FormNoBo:
        _bo_field_name = "max_teams"
        def __init__(self, data=None, instance=None):
            self.cleaned_data = {}
        def is_valid(self): return True
        def save(self, commit=False):
            saved["called"] = True
            return t

    monkeypatch.setattr(V, "TournamentSettingsForm", FormNoBo)
    r = c.post(reverse("tournaments:settings", args=[t.id]), data={"status": "upcoming"})
    assert r.status_code == 302
    assert saved["called"] is True

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_delete_tournament_get_and_post():
    staff = _mk_staff()
    t = Tournament.objects.create(name="DEL", start_date=timezone.now())
    from django.test import Client
    c = Client(); c.force_login(staff)
    r = c.get(reverse("tournaments:delete", args=[t.id]))
    assert r.status_code == 302 and "/settings" in r["Location"]

    r2 = c.post(reverse("tournaments:delete", args=[t.id]))
    assert r2.status_code == 302 and reverse("tournaments:list") in r2["Location"]
    assert not Tournament.objects.filter(id=t.id).exists()


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_generate_tournament_bracket_sends_ws(monkeypatch):
    staff = _mk_staff()
    t = Tournament.objects.create(name="GB", start_date=timezone.now())
    from django.test import Client
    c = Client(); c.force_login(staff)

    class DummyLayer:
        async def group_send(self, *a, **k): pass
    monkeypatch.setattr(V, "get_channel_layer", lambda: DummyLayer())
    monkeypatch.setattr(V, "generate_full_bracket", lambda _t: None)

    r = c.get(reverse("tournaments:generate_bracket", args=[t.id]))
    assert r.status_code == 302 and "/bracket" in r["Location"]


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_send_ws_update_async_and_sync(monkeypatch, make_team):
    t = Tournament.objects.create(name="WS", start_date=timezone.now())
    a = make_team("A"); b = make_team("B")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)

    class AsyncLayer:
        async def group_send(self, group, payload): 
            assert "bracket_update" in payload["type"]
    monkeypatch.setattr(V, "get_channel_layer", lambda: AsyncLayer())
    V.send_ws_update(m)

    class SyncLayer:
        def group_send(self, group, payload):
            assert "bracket_update" in payload["type"]
    monkeypatch.setattr(V, "get_channel_layer", lambda: SyncLayer())
    V.send_ws_update(m) 


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_register_team_no_more_slots_branch(make_team):
    u = User.objects.create_user("cap", password="x")
    team = make_team("CAP", captain=u)
    t = Tournament.objects.create(name="FULL", start_date=timezone.now(), max_teams=1,
                                  status="upcoming", registration_open=True)
    TournamentTeam.objects.create(tournament=t, team=team) 

    from django.test import Client
    c = Client(); c.force_login(u)

    r = c.get(reverse("tournaments:register_team", args=[t.id, team.id]))
    assert r.status_code == 302 and reverse("tournaments:overview", args=[t.id]) in r["Location"]

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_match_detail_post_with_code_calls_ban_and_builds_final_map(make_team, monkeypatch):
    a = make_team("A"); b = make_team("B")
    t = Tournament.objects.create(name="MD", start_date=timezone.now())
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)

    chosen = MAP_POOL[0][0]
    monkeypatch.setattr(Match, "available_map_codes", lambda self: [chosen, MAP_POOL[1][0]])

    monkeypatch.setattr(Match, "current_team", property(lambda self: a), raising=False)

    def _ban(self, code, team, action="ban"):
        self.final_map_code = MAP_POOL[1][0]
        return True
    monkeypatch.setattr(Match, "ban_map", _ban)

    class DummyLayer:
        async def group_send(self, group, payload):
            assert payload.get("type") == "match_update"
            return None

    monkeypatch.setattr(V, "get_channel_layer", lambda: DummyLayer())
    from django.test import Client
    c = Client()
    c.force_login(a.captain)

    r = c.post(reverse("tournaments:match_detail", args=[t.id, m.id]), data={"code": chosen})
    assert r.status_code == 302 and reverse("tournaments:match_detail", args=[t.id, m.id]) in r["Location"]

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_match_detail_get_builds_final_map_tuple(make_team):
    a = make_team("A"); b = make_team("B")
    t = Tournament.objects.create(name="MD2", start_date=timezone.now())
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    m.final_map_code = MAP_POOL[0][0]
    m.save(update_fields=["final_map_code"])

    from django.test import Client
    c = Client()
    c.force_login(a.captain)
    r = c.get(reverse("tournaments:match_detail", args=[t.id, m.id]))
    assert r.status_code == 200

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_settings_get_initial_with_missing_end_date():
    from django.test import Client
    staff = _mk_staff()
    c = Client(); c.force_login(staff)
    t = Tournament.objects.create(name="SET-MISS", start_date=timezone.now(), end_date=None)

    r = c.get(reverse("tournaments:settings", args=[t.id]))
    assert r.status_code == 200
    assert "SETTINGS" in r.content.decode()

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_match_detail_post_without_code_skips_ban_block(monkeypatch, make_team):
    a = make_team("A"); b = make_team("B")
    t = Tournament.objects.create(name="MD-NOCODE", start_date=timezone.now())
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    class DummyLayer:
        async def group_send(self, *a, **k): pass
    monkeypatch.setattr(V, "get_channel_layer", lambda: DummyLayer())

    from django.test import Client
    c = Client(); c.force_login(a.captain)

    r = c.post(reverse("tournaments:match_detail", args=[t.id, m.id]), data={})
    assert r.status_code == 302 and reverse("tournaments:match_detail", args=[t.id, m.id]) in r["Location"]

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_settings_forbidden_post_early_exit():
    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.create_user("plain", password="x")

    t = Tournament.objects.create(name="SET-FORBID", start_date=timezone.now())

    from django.test import Client
    c = Client(); c.force_login(u)
    r = c.post(reverse("tournaments:settings", args=[t.id]), data={"status": "upcoming"})
    assert r.status_code == 403

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_register_team_no_more_slots_redundant_branch_hit_via_instance_override(make_team, monkeypatch):
    from django.test import Client
    from tournaments.models import TournamentTeam, Tournament

    t = Tournament.objects.create(
        name="REG-FULL",
        start_date=timezone.now(),
        status="upcoming",
        registration_open=True,
        max_teams=1,
    )

    other = make_team("Other")
    TournamentTeam.objects.create(tournament=t, team=other)

    my = make_team("Mine")
    c = Client(); c.force_login(my.captain)

    monkeypatch.setattr(
        Tournament,
        "is_open_for_registration",
        property(lambda self: True),
        raising=False,
    )

    r = c.get(reverse("tournaments:register_team", args=[t.id, my.id]))
    assert r.status_code == 302
    assert reverse("tournaments:overview", args=[t.id]) in r["Location"]

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_settings_bo_field_false_branch(monkeypatch):
    staff = _mk_staff()
    from django.test import Client
    c = Client(); c.force_login(staff)
    t = Tournament.objects.create(
        name="SET-FALSE",
        start_date=timezone.now(),
        registration_open=False,
        max_teams=4,
    )

    captured = {"seen": {}}

    class FormSpy:
        _bo_field_name = "max_teams"
        def __init__(self, data=None, instance=None):
            captured["seen"] = dict(data or {})
            self.cleaned_data = {"max_teams": "4"}
        def is_valid(self): return True
        def save(self, commit=False): return instance

    instance = t
    monkeypatch.setattr(V, "TournamentSettingsForm", FormSpy)

    r = c.post(reverse("tournaments:settings", args=[t.id]), data={"status": "upcoming"})
    assert r.status_code == 302

    assert captured["seen"].get("registration_open") is None

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_settings_bo_field_name_missing_skips_setattr(monkeypatch):
    staff = _mk_staff()
    from django.test import Client
    c = Client(); c.force_login(staff)
    t = Tournament.objects.create(
        name="SET-MISS",
        start_date=timezone.now(),
        registration_open=True,
        max_teams=4,
    )
    class FormSpy:
        _bo_field_name = "max_teams"    
        def __init__(self, data=None, instance=None):
            self.cleaned_data = {} 
        def is_valid(self): return True
        def save(self, commit=False): return instance

    instance = t
    monkeypatch.setattr(V, "TournamentSettingsForm", FormSpy)
    r = c.post(reverse("tournaments:settings", args=[t.id]), data={"status": "upcoming"})
    assert r.status_code == 302

    t.refresh_from_db()
    assert t.max_teams == 4