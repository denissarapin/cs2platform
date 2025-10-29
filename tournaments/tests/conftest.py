# tests/conftest.py
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from teams.models import Team
from tournaments.models import Tournament, TournamentTeam

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user("user", password="x", email="u@u.u")

@pytest.fixture
def staff(db):
    return User.objects.create_user("admin", password="x", is_staff=True, email="a@a.a")

@pytest.fixture
def make_user(db):
    def _make(username):
        return User.objects.create_user(username, password="x", email=f"{username}@x.x")
    return _make

@pytest.fixture
def make_team(db, make_user):
    def _make(name, tag=None, captain=None):
        cap = captain or make_user(f"{name.lower()}_cap")
        return Team.objects.create(name=name, tag=tag or name[:3].upper(), captain=cap)
    return _make

@pytest.fixture
def tournament(db):
    # делаем aware datetime, чтобы не ругалось на naive
    return Tournament.objects.create(name="Cup", start_date=timezone.now())

@pytest.fixture
def two_registered_teams(db, tournament, make_team):
    a = make_team("Alpha", "A")
    b = make_team("Bravo", "B")
    TournamentTeam.objects.create(tournament=tournament, team=a)
    TournamentTeam.objects.create(tournament=tournament, team=b)
    return (a, b)
