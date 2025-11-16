import pytest
from unittest.mock import patch
from django.test import override_settings
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from tournaments.models import Tournament, TournamentTeam, Match, MapBan, MAP_POOL
from teams.models import Team
from tournaments import views as V

User = get_user_model()

LOC_TPL = {
    "tournaments/matches.html": "MATCHES {{ matches|length }}",
    "tournaments/teams.html": "TEAMS {{ participants|length }}",
    "tournaments/results.html": "RESULTS {{ matches|length }}",
    "tournaments/_report_form.html": "REPORT {% if error %}ERR:{{ error }}{% endif %}",
    "tournaments/match_detail.html": "DETAIL {{ match.id }} {% if final_map %}FINAL{{ final_map.0 }}{% endif %}",
    "tournaments/match_detail_inner.html": "INNER {{ match.id }} {% if final_map %}FINAL{{ final_map.0 }}{% endif %}",
    "tournaments/_veto_panel.html": "VETO {% if final_map %}FINAL{% endif %}{% if current_team %} CUR={{ current_team.id }}{% endif %}"
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


def _staff():
    return User.objects.create_user("s", password="x", is_staff=True, email="s@s.s")


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_tournament_matches_teams_results_views(make_team):
    t = Tournament.objects.create(name="V", start_date=timezone.now())
    a = make_team("A"); b = make_team("B")
    Match.objects.create(tournament=t, team_a=a, team_b=b, status="finished")
    TournamentTeam.objects.create(tournament=t, team=a)
    TournamentTeam.objects.create(tournament=t, team=b)

    from django.test import Client
    c = Client(); c.force_login(_staff())

    r1 = c.get(reverse("tournaments:matches", args=[t.id])); assert "MATCHES 1" in r1.content.decode()
    r2 = c.get(reverse("tournaments:teams", args=[t.id]));   assert "TEAMS 2" in r2.content.decode()
    r3 = c.get(reverse("tournaments:results", args=[t.id])); assert "RESULTS 1" in r3.content.decode()


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_report_match_result_get_and_post_paths(make_team, monkeypatch):
    t = Tournament.objects.create(name="R", start_date=timezone.now())
    a = make_team("A"); b = make_team("B")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)

    from django.test import Client
    c = Client(); c.force_login(_staff())

    r_get = c.get(reverse("tournaments:report_match", args=[t.id, m.id]))
    assert r_get.status_code == 200 and "REPORT" in r_get.content.decode()

    r_bad = c.post(reverse("tournaments:report_match", args=[t.id, m.id]), data={"score_a": "x", "score_b": "1"})
    assert r_bad.status_code == 302 and reverse("tournaments:matches", args=[t.id]) in r_bad["Location"]

    r_bad_h = c.post(reverse("tournaments:report_match", args=[t.id, m.id]), data={"score_a": "x", "score_b": "y"}, HTTP_HX_REQUEST="true")
    assert r_bad_h.status_code == 400 and "ERR:Invalid score format" in r_bad_h.content.decode()

    sm = {"called": 0}; up = {"called": 0}
    monkeypatch.setattr(V, "set_match_result", lambda _m, a, b: sm.__setitem__("called", 1))
    monkeypatch.setattr(V, "update_bracket_progression", lambda _t: up.__setitem__("called", 1))
    monkeypatch.setattr(V, "send_ws_update", lambda _m: None)

    r_ok = c.post(reverse("tournaments:report_match", args=[t.id, m.id]), data={"score_a": "2", "score_b": "1"})
    assert r_ok.status_code == 302 and reverse("tournaments:matches", args=[t.id]) in r_ok["Location"]
    assert sm["called"] == 1 and up["called"] == 1

    r_ok_h = c.post(reverse("tournaments:report_match", args=[t.id, m.id]), data={"score_a": "1", "score_b": "0"}, HTTP_HX_REQUEST="true")
    assert r_ok_h.status_code == 204 and r_ok_h["HX-Trigger"] == "match-updated"


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_register_team_all_branches(make_team):
    u = User.objects.create_user("cap", password="x")
    cap_team = make_team("CPT", captain=u)
    other = make_team("OTR")
    t = Tournament.objects.create(name="Reg", start_date=timezone.now(), max_teams=1, registration_open=True)
    from django.test import Client
    c = Client(); c.force_login(u)
    r1 = c.get(reverse("tournaments:register_team", args=[t.id, other.id]))
    assert r1.status_code == 302
    t.registration_open = False; t.save(update_fields=["registration_open"])
    r2 = c.get(reverse("tournaments:register_team", args=[t.id, cap_team.id]))
    assert r2.status_code == 302
    t.registration_open = True; t.save(update_fields=["registration_open"])
    TournamentTeam.objects.create(tournament=t, team=other)
    r3 = c.get(reverse("tournaments:register_team", args=[t.id, cap_team.id]))
    assert r3.status_code == 302
    t2 = Tournament.objects.create(name="Reg2", start_date=timezone.now(), max_teams=8, registration_open=True)
    r4 = c.get(reverse("tournaments:register_team", args=[t2.id, cap_team.id]))
    assert r4.status_code == 302 and f"?joined={cap_team.id}" in r4["Location"]


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_match_detail_get_and_post(make_team, monkeypatch):
    t = Tournament.objects.create(name="MD", start_date=timezone.now())
    a = make_team("A"); b = make_team("B")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    class Layer:
        async def group_send(self, *a, **k): pass
    monkeypatch.setattr(V, "get_channel_layer", lambda: Layer())
    from django.test import Client
    c = Client(); c.force_login(_staff())
    r_get = c.get(reverse("tournaments:match_detail", args=[t.id, m.id]))
    assert r_get.status_code == 200
    assert "DETAIL" in r_get.content.decode()
    r_post = c.post(reverse("tournaments:match_detail", args=[t.id, m.id]), data={"map_name": "de_nonexist"})
    assert r_post.status_code == 302
    all_codes = [c for c, _ in MAP_POOL]
    keep = all_codes[:2]
    for i, code in enumerate(all_codes[2:], start=1):
        MapBan.objects.create(match=m, team=a, map_name=code, order=i, action=MapBan.Action.BAN)
    m.start_veto(now=timezone.now())
    curr = a if (m.map_bans.count() % 2 == 0) else b
    V.perform_ban(m, curr, keep[0])
    r_post2 = c.post(reverse("tournaments:match_detail", args=[t.id, m.id]), data={"map_name": keep[0]})
    assert r_post2.status_code == 302  


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_match_veto_get_and_post_paths(make_team):
    uA = User.objects.create_user("capA", password="x")
    uB = User.objects.create_user("capB", password="x")
    a = make_team("A", captain=uA); b = make_team("B", captain=uB)
    t = Tournament.objects.create(name="Veto", start_date=timezone.now())
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    from django.test import Client
    c = Client()
    c.force_login(uA)
    r_get = c.get(reverse("tournaments:match_veto", args=[t.id, m.id]))
    assert r_get.status_code == 200 and "VETO" in r_get.content.decode()
    r_no = c.post(reverse("tournaments:match_veto", args=[t.id, m.id]), data={})
    assert r_no.status_code == 302
    c.logout(); c.force_login(uB)
    r_wrong_turn = c.post(reverse("tournaments:match_veto", args=[t.id, m.id]), data={"map_name": MAP_POOL[0][0]})
    assert r_wrong_turn.status_code == 302
    c.logout(); c.force_login(uA)
    code = MAP_POOL[1][0]
    r_ok = c.post(reverse("tournaments:match_veto", args=[t.id, m.id]), data={"map_name": code})
    assert r_ok.status_code == 302
    r_dup = c.post(reverse("tournaments:match_veto", args=[t.id, m.id]), data={"map_name": code})
    assert r_dup.status_code == 302

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_get_final_map_single_available(make_team):
    t = Tournament.objects.create(name="GFM", start_date=timezone.now())
    a = make_team("A"); b = make_team("B")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    pool = [c for c, _ in MAP_POOL]
    keep = pool[0]
    for i, code in enumerate(pool[1:], start=1):
        MapBan.objects.create(match=m, team=a, map_name=code, order=i)
    only = V.get_final_map(m)
    assert only[0] == keep 


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_perform_ban_returns_false_for_unavailable_map(make_team):
    t = Tournament.objects.create(name="PBFalse", start_date=timezone.now())
    a = make_team("A"); b = make_team("B")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    assert V.perform_ban(m, a, "de_not_exists") is False


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_match_veto_post_map_already_unavailable_shows_error(make_team):
    uA = User.objects.create_user("capA", password="x")
    a = make_team("A", captain=uA)
    uB = User.objects.create_user("capB", password="x")
    b = make_team("B", captain=uB)
    t = Tournament.objects.create(name="VetoErr", start_date=timezone.now())
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    code = [c for c, _ in MAP_POOL][0]
    MapBan.objects.create(match=m, team=a, map_name=code, order=1)
    from django.test import Client
    c = Client(); c.force_login(uA)
    r = c.post(reverse("tournaments:match_veto", args=[t.id, m.id]), data={"map_name": code})
    assert r.status_code == 302 and reverse("tournaments:match_veto", args=[t.id, m.id]) in r["Location"]

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_match_veto_sets_current_team_on_get(make_team):
    uA = User.objects.create_user("capA", password="x")
    uB = User.objects.create_user("capB", password="x")
    a = make_team("A", captain=uA); b = make_team("B", captain=uB)
    t = Tournament.objects.create(name="V1", start_date=timezone.now())
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    from django.test import Client
    c = Client(); c.force_login(uA)
    r = c.get(reverse("tournaments:match_veto", args=[t.id, m.id]))
    assert r.status_code == 200

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_match_veto_map_already_unavailable_error_branch(make_team, monkeypatch):
    uA = User.objects.create_user("capA", password="x")
    uB = User.objects.create_user("capB", password="x")
    a = make_team("A", captain=uA); b = make_team("B", captain=uB)
    t = Tournament.objects.create(name="V2", start_date=timezone.now())
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    chosen = MAP_POOL[0][0]
    other  = MAP_POOL[1][0]
    monkeypatch.setattr(V, "get_available_maps", lambda match: [(chosen, "X"), (other, "Y")])
    monkeypatch.setattr(V, "perform_ban", lambda match, team, mapname: False)
    from django.test import Client
    c = Client(); c.force_login(uA)
    r = c.post(reverse("tournaments:match_veto", args=[t.id, m.id]), data={"map_name": chosen})
    assert r.status_code == 302
    assert reverse("tournaments:match_veto", args=[t.id, m.id]) in r["Location"]

@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
def test_match_veto_post_without_teams_skips_current_team_branch(make_team):
    t = Tournament.objects.create(name="VETO-NOTEAMS", start_date=timezone.now())
    m = Match.objects.create(tournament=t, team_a=None, team_b=None)
    from django.test import Client
    u = make_team("X").captain 
    c = Client(); c.force_login(u)
    r = c.post(reverse("tournaments:match_veto", args=[t.id, m.id]), data={"map_name": "de_mirage"})
    assert r.status_code == 302 and reverse("tournaments:match_veto", args=[t.id, m.id]) in r["Location"]