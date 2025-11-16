import pytest
from django.utils import timezone
from django.contrib.auth import get_user_model
from tournaments.models import Tournament, Match, MapBan, MAP_POOL, TournamentTeam
from teams.models import Team

User = get_user_model()

@pytest.mark.django_db
def test_start_veto_twice_is_noop(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=10)

    now = timezone.now()
    m.start_veto(now=now)
    m.refresh_from_db()

    assert m.veto_state == "running"
    assert m.veto_started_at == now
    assert m.veto_deadline == now + timezone.timedelta(seconds=10)
    assert m.veto_turn == "A"

    later = now + timezone.timedelta(seconds=5)
    m.start_veto(now=later)
    m.refresh_from_db()

    assert m.veto_state == "running"
    assert m.veto_started_at == now
    assert m.veto_deadline == now + timezone.timedelta(seconds=10)
    assert m.veto_turn == "A"

@pytest.mark.django_db
def test_ban_map_rejects_invalid_code(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=10)

    m.start_veto(now=timezone.now())
    assert m.ban_map("de_notexist", a, action="ban") is False


@pytest.mark.django_db
def test_ban_map_wrong_turn_returns_false(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=10)

    m.start_veto(now=timezone.now())
    some_code = [c for c, _ in MAP_POOL][0]
    assert m.ban_map(some_code, b, action="ban") is False


@pytest.mark.django_db
def test_ban_map_already_banned_returns_false(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=10)

    code = [c for c, _ in MAP_POOL][0]
    MapBan.objects.create(match=m, team=a, map_name=code, order=1, action=MapBan.Action.BAN)

    m.start_veto(now=timezone.now())
    assert m.ban_map(code, a, action="ban") is False

@pytest.mark.django_db
def test_auto_ban_if_expired_no_change_when_not_running(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=5)

    assert m.auto_ban_if_expired(now=timezone.now()) is False


@pytest.mark.django_db
def test_auto_ban_if_expired_not_past_deadline(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=5)
    start = timezone.now()
    m.start_veto(now=start)

    assert m.auto_ban_if_expired(now=start + timezone.timedelta(seconds=4)) is False

@pytest.mark.django_db
def test_available_map_codes_empty_when_final_set(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    m.final_map_code = [c for c, _ in MAP_POOL][1]
    m.save(update_fields=["final_map_code"])

    assert m.available_map_codes() == []


@pytest.mark.django_db
def test_str_representations(make_team):
    t = Tournament.objects.create(name="Spring Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)

    assert str(t)
    assert str(m)

    code = [c for c, _ in MAP_POOL][0]
    ban = MapBan.objects.create(match=m, team=a, map_name=code, order=1, action=MapBan.Action.BAN)
    assert str(ban)

@pytest.mark.django_db
def test_ban_map_before_start_returns_false(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=10)

    code = [c for c, _ in MAP_POOL][0]
    assert m.ban_map(code, a, action="ban") is False

@pytest.mark.django_db
def test_ban_map_from_third_team_returns_false(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    third = make_team("Charlie")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=10)

    m.start_veto(now=timezone.now())
    code = [c for c, _ in MAP_POOL][0]
    assert m.ban_map(code, third, action="ban") is False

@pytest.mark.django_db
def test_auto_ban_if_expired_finalizes_when_two_left(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=5)

    all_codes = [c for c, _ in MAP_POOL]
    keep = all_codes[:2]      
    preban = all_codes[2:]     
    for i, code in enumerate(preban, start=1):
        MapBan.objects.create(match=m, team=a, map_name=code, order=i, action=MapBan.Action.BAN)

    start = timezone.now()
    m.start_veto(now=start)

    assert set(m.available_map_codes()) == set(keep)
    later = start + timezone.timedelta(seconds=6)
    _ = m.auto_ban_if_expired(now=later)
    m.refresh_from_db()

    assert m.veto_state == "done"
    assert m.final_map_code in keep
    assert m.available_map_codes() == []

@pytest.mark.django_db
def test_available_map_codes_before_start_respects_prebans(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)

    all_codes = [c for c, _ in MAP_POOL]
    banned = set(all_codes[:3])
    left = [c for c in all_codes if c not in banned]

    for i, code in enumerate(all_codes[:3], start=1):
        MapBan.objects.create(match=m, team=a, map_name=code, order=i, action=MapBan.Action.BAN)

    assert set(m.available_map_codes()) == set(left)

@pytest.mark.django_db
def test_connect_string_empty_when_no_addr(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, server_addr="")
    assert not m.connect_string

@pytest.mark.django_db
def test_mapban_pick_action_str(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)

    code = [c for c, _ in MAP_POOL][0]
    pick = MapBan.objects.create(match=m, team=a, map_name=code, order=1, action=MapBan.Action.PICK)
    assert str(pick) 


@pytest.mark.django_db
def test_tournamentteam_str(make_team):
    t = Tournament.objects.create(name="TT Cup", start_date=timezone.now())
    team = make_team("Alpha")
    tt = TournamentTeam.objects.create(tournament=t, team=team)
    s = str(tt)
    assert team.name in s and t.name in s

@pytest.mark.django_db
def test_match_is_finished_property(make_team):
    t = Tournament.objects.create(name="Prop Cup", start_date=timezone.now())
    a = make_team("A")
    b = make_team("B")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, status="scheduled")
    assert m.is_finished is False

    m.status = "finished"
    m.save(update_fields=["status"])
    assert m.is_finished is True


@pytest.mark.django_db
def test_match_current_team_none_when_team_missing(make_team):
    t = Tournament.objects.create(name="CT Cup", start_date=timezone.now())
    a = make_team("OnlyA")
    m = Match.objects.create(tournament=t, team_a=a, team_b=None)
    assert m.current_team is None

@pytest.mark.django_db
def test_auto_ban_if_expired_returns_false_when_no_available_maps(make_team):
    t = Tournament.objects.create(name="NoAvail Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=1)

    all_codes = [c for c, _ in MAP_POOL]
    for i, code in enumerate(all_codes, start=1):
        MapBan.objects.create(match=m, team=a, map_name=code, order=i, action=MapBan.Action.BAN)
    start = timezone.now()
    m.start_veto(now=start)
    later = start + timezone.timedelta(seconds=5)
    assert m.auto_ban_if_expired(now=later) is False

@pytest.mark.django_db
def test_set_result_draw_resets_status_from_finished(make_team):
    t = Tournament.objects.create(name="Result Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, status="finished")

    m.set_result(3, 3)
    m.refresh_from_db()
    assert m.winner is None
    assert m.status == "scheduled"


@pytest.mark.django_db
def test_set_result_draw_resets_status_if_was_finished(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now(), status="finished")
    a = make_team("A")
    b = make_team("B")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, status="finished")
    m.set_result(5, 5)
    m.refresh_from_db()
    assert m.winner is None
    assert m.status == "scheduled"

@pytest.mark.django_db
def test_auto_ban_if_expired_no_avail_maps_returns_false(make_team, monkeypatch):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("A")
    b = make_team("B")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=1)
    m.start_veto(now=timezone.now())
    monkeypatch.setattr(Match, "available_map_codes", lambda self: [])
    later = timezone.now() + timezone.timedelta(seconds=2)
    assert m.auto_ban_if_expired(now=later) is False

@pytest.mark.django_db
def test_after_action_tick_final_map_does_not_override_existing_server_addr(make_team):
    t = Tournament.objects.create(name="AddrKeep", start_date=timezone.now())
    a = make_team("Alpha"); b = make_team("Bravo")
    m = Match.objects.create(
        tournament=t, team_a=a, team_b=b, veto_timeout=5,
        server_addr="10.0.0.5:27015",
    )

    all_codes = [c for c, _ in MAP_POOL]
    keep = all_codes[:2]
    preban = all_codes[2:]
    for i, code in enumerate(preban, start=1):
        MapBan.objects.create(match=m, team=a, map_name=code, order=i, action=MapBan.Action.BAN)

    now = timezone.now()
    m.start_veto(now=now)
    m.refresh_from_db()

    current_team = a if (m.map_bans.count() % 2 == 0) else b
    assert m.ban_map(keep[0], current_team, action="ban") is True

    m.refresh_from_db()
    assert m.veto_state == "done"
    assert m.final_map_code == keep[1]
    assert m.server_addr == "10.0.0.5:27015"


@pytest.mark.django_db
def test_set_result_tie_when_not_finished_keeps_status(make_team):

    t = Tournament.objects.create(name="TieKeep", start_date=timezone.now())
    a = make_team("Alpha"); b = make_team("Bravo")
    m = Match.objects.create(
        tournament=t, team_a=a, team_b=b,
        status="scheduled",  
        score_a=1, score_b=0,
    )

    m.set_result(9, 9) 
    m.refresh_from_db()
    assert m.winner is None
    assert m.status == "scheduled"  
    assert (m.score_a, m.score_b) == (9, 9)