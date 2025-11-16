import pytest
from django.utils import timezone
from tournaments.models import Tournament, TournamentTeam, Match, MAP_POOL
from tournaments.services import (
    generate_full_bracket,
    update_bracket_progression,
    set_match_result,
    get_available_maps,
    perform_ban,
    get_final_map,
)
from tournaments import services


@pytest.mark.django_db
def test_generate_bracket_creates_round1_matches(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("A", "A")
    b = make_team("B", "B")
    TournamentTeam.objects.create(tournament=t, team=a)
    TournamentTeam.objects.create(tournament=t, team=b)

    generate_full_bracket(t)

    assert Match.objects.filter(tournament=t, round=1).count() == 1
    assert Match.objects.filter(tournament=t).exists()

@pytest.mark.django_db
def test_generate_bracket_with_bye_marks_finished_and_has_winner(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    for n in ["A", "B", "C"]:
        TournamentTeam.objects.create(tournament=t, team=make_team(n, n))

    generate_full_bracket(t)
    r1 = list(Match.objects.filter(tournament=t, round=1).order_by("id"))
    assert any(m.status == "finished" and m.winner_id for m in r1)

@pytest.mark.django_db
def test_update_bracket_progression_propagates_winners(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    for n in ["A", "B", "C", "D", "E"]:
        TournamentTeam.objects.create(tournament=t, team=make_team(n, n))

    generate_full_bracket(t)
    update_bracket_progression(t)
    assert Match.objects.filter(tournament=t).count() >= 3

@pytest.mark.django_db
def test_generate_bracket_raises_when_less_than_two_teams(make_team):
    t = Tournament.objects.create(name="TooFew", start_date=timezone.now())
    with pytest.raises(ValueError):
        generate_full_bracket(t)

    t1 = Tournament.objects.create(name="One", start_date=timezone.now())
    TournamentTeam.objects.create(tournament=t1, team=make_team("Solo", "S"))
    with pytest.raises(ValueError):
        generate_full_bracket(t1)

@pytest.mark.django_db
def test_generate_bracket_raises_when_one_team(make_team):
    t = Tournament.objects.create(name="OneTeam", start_date=timezone.now())
    TournamentTeam.objects.create(tournament=t, team=make_team("Solo", "S"))
    with pytest.raises(ValueError):
        generate_full_bracket(t)

@pytest.mark.django_db
def test_set_match_result_finishes_and_sets_winner(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("A", "A")
    b = make_team("B", "B")
    m = Match.objects.create(tournament=t, round=1, team_a=a, team_b=b, status="scheduled")

    set_match_result(m, 16, 8)
    m.refresh_from_db()
    assert m.status == "finished"
    assert m.winner_id == a.id
    assert (m.score_a, m.score_b) == (16, 8)

@pytest.mark.django_db
def test_set_match_result_tie_resets_to_scheduled(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("A", "A")
    b = make_team("B", "B")
    m = Match.objects.create(tournament=t, round=1, team_a=a, team_b=b, status="scheduled")

    set_match_result(m, 10, 10)
    m.refresh_from_db()
    assert m.status == "scheduled"
    assert m.winner is None

@pytest.mark.django_db
def test_available_maps_and_ban_flow(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("A", "A")
    b = make_team("B", "B")
    m = Match.objects.create(tournament=t, round=1, team_a=a, team_b=b, status="scheduled")

    codes = [c for c, _ in MAP_POOL]
    assert get_available_maps(m) == codes

    assert perform_ban(m, a, codes[0]) is True
    assert codes[0] not in get_available_maps(m)

@pytest.mark.django_db
def test_get_final_map_when_one_left(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("A", "A")
    b = make_team("B", "B")
    m = Match.objects.create(tournament=t, round=1, team_a=a, team_b=b, status="scheduled")

    codes = [c for c, _ in MAP_POOL]
    for code in codes[:-1]:
        perform_ban(m, a, code)

    fm = get_final_map(m)
    assert fm is not None
    assert fm[0] == codes[-1]


pytest.mark.django_db
def test_get_final_map_is_none_when_multiple_maps_left(make_team):
    t = Tournament.objects.create(name="MapsNone", start_date=timezone.now())
    a = make_team("A", "A")
    b = make_team("B", "B")
    m = Match.objects.create(tournament=t, round=1, team_a=a, team_b=b, status="scheduled")

    assert get_final_map(m) is None

@pytest.mark.django_db
def test_perform_ban_duplicate_returns_false(make_team):
    t = Tournament.objects.create(name="DupBan", start_date=timezone.now())
    a = make_team("A", "A")
    b = make_team("B", "B")
    m = Match.objects.create(tournament=t, round=1, team_a=a, team_b=b, status="scheduled")

    first_code = MAP_POOL[0][0]
    assert perform_ban(m, a, first_code) is True 
    assert perform_ban(m, a, first_code) is False

@pytest.mark.django_db
def test_update_bracket_progression_sets_tournament_winner(make_team):
    t = Tournament.objects.create(name="Finish", start_date=timezone.now())
    a = make_team("A", "A")
    b = make_team("B", "B")
    TournamentTeam.objects.create(tournament=t, team=a)
    TournamentTeam.objects.create(tournament=t, team=b)

    generate_full_bracket(t)

    m = Match.objects.get(tournament=t, round=1)

    if m.team_a_id == a.id:
        set_match_result(m, 16, 8)
    else:
        set_match_result(m, 8, 16)

    update_bracket_progression(t)
    t.refresh_from_db()

    assert t.status == "finished"
    assert t.winner_id == a.id

@pytest.mark.django_db
def test_update_bracket_progression_no_matches_returns_silently():
    from tournaments.services import update_bracket_progression
    t = Tournament.objects.create(name="Empty", start_date=timezone.now())
    update_bracket_progression(t)
    t.refresh_from_db()
    assert t.status in (None, "upcoming", "created", "draft", "scheduled")


@pytest.mark.django_db
def test_update_bracket_progression_skips_when_next_round_is_too_short(make_team):
    from tournaments.services import update_bracket_progression, set_match_result
    t = Tournament.objects.create(name="Skips", start_date=timezone.now())

    a1, b1 = make_team("A1", "A1"), make_team("B1", "B1")
    a2, b2 = make_team("A2", "A2"), make_team("B2", "B2")
    a3, b3 = make_team("A3", "A3"), make_team("B3", "B3")

    m1 = Match.objects.create(tournament=t, round=1, team_a=a1, team_b=b1, status="scheduled")
    m2 = Match.objects.create(tournament=t, round=1, team_a=a2, team_b=b2, status="scheduled")
    m3 = Match.objects.create(tournament=t, round=1, team_a=a3, team_b=b3, status="scheduled")

    nx = Match.objects.create(tournament=t, round=2, status="scheduled")

    set_match_result(m1, 16, 0)
    set_match_result(m2, 16, 0)
    set_match_result(m3, 16, 0)

    update_bracket_progression(t)
    nx.refresh_from_db()

    assert nx.team_a_id == m1.winner_id
    assert nx.team_b_id == m2.winner_id
    assert nx.team_a_id in (a1.id, b1.id)
    assert nx.team_b_id in (a2.id, b2.id)


@pytest.mark.django_db
def test_update_bracket_progression_final_sets_winner_and_end_date(make_team):
    from tournaments.services import generate_full_bracket, set_match_result, update_bracket_progression
    t = Tournament.objects.create(name="Finals", start_date=timezone.now())
    a = make_team("FA", "FA")
    b = make_team("FB", "FB")
    TournamentTeam.objects.create(tournament=t, team=a)
    TournamentTeam.objects.create(tournament=t, team=b)

    generate_full_bracket(t)
    m = Match.objects.get(tournament=t, round=1)

    if m.team_a_id == a.id:
        set_match_result(m, 16, 8)
    else:
        set_match_result(m, 8, 16)

    if not m.scheduled_at:
        m.scheduled_at = timezone.now()
        m.save(update_fields=["scheduled_at"])

    update_bracket_progression(t)
    t.refresh_from_db()

    assert t.status == "finished"
    assert t.winner_id == a.id
    assert t.end_date is not None

@pytest.mark.django_db
def test_set_match_result_when_one_team_missing_sets_no_winner(make_team):
    t = Tournament.objects.create(name="NoOpponent", start_date=timezone.now())
    a = make_team("A", "A")

    m = Match.objects.create(tournament=t, round=1, team_a=a, team_b=None, status="scheduled")

    set_match_result(m, 16, 0)
    m.refresh_from_db()

    assert m.status == "finished"
    assert m.winner is None
    assert (m.score_a, m.score_b) == (16, 0)


@pytest.mark.django_db
def test_perform_ban_rejects_invalid_map(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("A"); b = make_team("B")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, veto_timeout=10)
    m.start_veto(now=timezone.now())
    assert perform_ban(m, a, "de_not_exist") is False

@pytest.mark.django_db
def test_update_bracket_progression_does_not_save_when_slots_already_set(make_team):

    t = Tournament.objects.create(name="NoSave", start_date=timezone.now())

    a1, b1 = make_team("A1", "A1"), make_team("B1", "B1")
    a2, b2 = make_team("A2", "A2"), make_team("B2", "B2")
    m1 = Match.objects.create(tournament=t, round=1, team_a=a1, team_b=b1, status="scheduled")
    m2 = Match.objects.create(tournament=t, round=1, team_a=a2, team_b=b2, status="scheduled")

    target = Match.objects.create(tournament=t, round=2, status="scheduled")

    set_match_result(m1, 16, 0)
    set_match_result(m2, 16, 0)

    target.team_a = a1
    target.team_b = a2
    target.save(update_fields=["team_a", "team_b"])

    update_bracket_progression(t)

    target.refresh_from_db()
    assert target.team_a_id == a1.id
    assert target.team_b_id == a2.id


@pytest.mark.django_db
def test_update_bracket_progression_final_already_finished_noop(make_team):

    t = Tournament.objects.create(name="FinalNoop", start_date=timezone.now())
    a = make_team("A", "A")
    b = make_team("B", "B")

    m = Match.objects.create(tournament=t, round=1, team_a=a, team_b=b, status="scheduled")
    set_match_result(m, 16, 0)

    t.winner = a
    t.status = "finished"
    if not m.scheduled_at:
        m.scheduled_at = timezone.now()
        m.save(update_fields=["scheduled_at"])
    end_at_before = timezone.now()
    t.end_date = end_at_before
    t.save(update_fields=["winner", "status", "end_date"])

    update_bracket_progression(t)

    t.refresh_from_db()
    assert t.winner_id == a.id
    assert t.status == "finished"
    assert t.end_date == end_at_before


@pytest.mark.django_db
def test_update_bracket_progression_multiple_finals_len_not_one_exits():
    t = Tournament.objects.create(name="WeirdFinals", start_date=timezone.now())
    Match.objects.create(tournament=t, round=3, status="scheduled")
    Match.objects.create(tournament=t, round=3, status="scheduled")

    update_bracket_progression(t)
    t.refresh_from_db()

    assert t.status in (None, "upcoming", "created", "draft", "scheduled")
    assert t.winner_id is None