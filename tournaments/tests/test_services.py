# tournaments/tests/test_services.py
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

# === Генерация сетки ===

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

# === Результаты матчей ===

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

# === Работа с картами (ban/pool) ===

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
