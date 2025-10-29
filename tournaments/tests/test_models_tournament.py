import pytest
from django.utils import timezone
from tournaments.models import Tournament, TournamentTeam

@pytest.mark.django_db
def test_is_open_for_registration_when_upcoming_and_open_and_has_slots():
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="upcoming",
        registration_open=True,
        max_teams=2,
    )
    # без участников и открыта — True
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
    team = make_team(name="A", tag="A")  # фикстура создаст команду с капитаном
    TournamentTeam.objects.create(tournament=t, team=team)

    assert t.is_open_for_registration is False