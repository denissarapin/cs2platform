import pytest
from django.utils import timezone
from tournaments.models import Tournament, TournamentTeam, Match, MapBan
from teams.models import Team
from django.db import IntegrityError

pytestmark = pytest.mark.django_db

@pytest.mark.django_db
def test_is_open_for_registration_when_upcoming_and_open_and_has_slots():
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="upcoming",
        registration_open=True,
        max_teams=2,
    )
    assert t.is_open_for_registration is True

@pytest.mark.django_db
def test_is_open_for_registration_closed_flag():
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="upcoming",
        registration_open=False,
        max_teams=16,
    )
    assert t.is_open_for_registration is False

@pytest.mark.django_db
def test_is_open_for_registration_not_upcoming():
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="running",
        registration_open=True,
        max_teams=16,
    )
    assert t.is_open_for_registration is False

@pytest.mark.django_db
def test_is_open_for_registration_no_slots(make_team):
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="upcoming",
        registration_open=True,
        max_teams=1,
    )
    team = make_team(name="A", tag="A")
    TournamentTeam.objects.create(tournament=t, team=team)

    assert t.is_open_for_registration is False

@pytest.mark.django_db
def test_mapban_unique_per_match(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b)
    MapBan.objects.create(match=m, team=a, map_name="de_mirage", order=1)
    with pytest.raises(IntegrityError):
        MapBan.objects.create(match=m, team=b, map_name="de_mirage", order=2)


@pytest.mark.django_db
def test_match_check_constraint_same_teams_forbidden(make_team):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a = make_team("Alpha")

    with pytest.raises(IntegrityError):
        Match.objects.create(tournament=t, team_a=a, team_b=a)


def test_slots_left_when_empty_and_partial(make_team):
    t = Tournament.objects.create(
        name="Slots", start_date=timezone.now(),
        status="upcoming", registration_open=True, max_teams=4
    )
    assert t.participants.count() == 0
    assert t.slots_left == 4 

    a = make_team("Alpha")
    TournamentTeam.objects.create(tournament=t, team=a)
    assert t.participants.count() == 1
    assert t.slots_left == 3


def test_slots_left_clamped_to_zero_when_full_or_overfilled(make_team):
    t = Tournament.objects.create(
        name="SlotsClamp", start_date=timezone.now(),
        status="upcoming", registration_open=True, max_teams=2
    )
    a = make_team("Alpha")
    b = make_team("Bravo")
    TournamentTeam.objects.create(tournament=t, team=a)
    TournamentTeam.objects.create(tournament=t, team=b)
    t.refresh_from_db()
    assert t.participants.count() == 2
    assert t.slots_left == 0

    c = make_team("Charlie")
    TournamentTeam.objects.create(tournament=t, team=c)
    t.refresh_from_db()
    assert t.participants.count() == 3
    assert t.slots_left == 0 