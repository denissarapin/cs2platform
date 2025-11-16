import datetime as dt
import uuid
import pytest
from django.template import engines
import copy
TEMPLATES_MAP = {
    "teams/my_teams.html": "OK my_teams",
    "teams/team_create.html": "OK team_create {{ form }}",
    "teams/team_detail.html": "OK team_detail",
    "teams/_user_search_results.html": "OK user_search",
    "teams/_invite_response_bundle.html": "OK invite_bundle",
    "teams/_invites_outgoing.html": "OK invites_outgoing",
    "teams/_notif_count.html": "OK notif_count {{ pending_count }} {{ count }}",
    "teams/_notif_panel.html": "OK notif_panel",
}

@pytest.fixture(autouse=True)
def _override_templates(settings):
    prev = copy.deepcopy(settings.TEMPLATES)
    new_tpl = copy.deepcopy(settings.TEMPLATES)
    new_tpl[0]["APP_DIRS"] = False
    new_tpl[0].setdefault("OPTIONS", {})["loaders"] = [
        ("django.template.loaders.locmem.Loader", TEMPLATES_MAP),
        "django.template.loaders.filesystem.Loader",
        "django.template.loaders.app_directories.Loader",  
    ]
    settings.TEMPLATES = new_tpl
    engines._engines.clear()
    yield
    settings.TEMPLATES = prev
    engines._engines.clear()

@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="u1", email="u1@example.com", password="pass123"
    )

@pytest.fixture
def another_user(django_user_model):
    return django_user_model.objects.create_user(
        username="u2", email="u2@example.com", password="pass123"
    )

@pytest.fixture
def third_user(django_user_model):
    return django_user_model.objects.create_user(
        username="u3", email="u3@example.com", password="pass123"
    )

@pytest.fixture
def captain_user(django_user_model):
    return django_user_model.objects.create_user(
        username="cap", email="cap@example.com", password="pass123"
    )

@pytest.fixture
def team(captain_user):
    from teams.models import Team, TeamMembership
    t = Team.objects.create(name="Dream Team", tag="DT", slug="dream-team", captain=captain_user)
    TeamMembership.objects.create(user=captain_user, team=t, role="captain")
    return t

@pytest.fixture
def logged_client(client, user):
    client.login(username="u1", password="pass123")
    return client

@pytest.fixture
def captain_client(client, captain_user):
    client.login(username="cap", password="pass123")
    return client

@pytest.fixture
def invite_factory(team, captain_user):
    from teams.models import TeamInvite
    def _mk(invited_user, status=None, code=None, created_delta=0):
        st = status or TeamInvite.Status.PENDING
        obj = TeamInvite.objects.create(
            team=team,
            invited_user=invited_user,
            invited_by=captain_user,
            status=st,
            code=code or uuid.uuid4(),
        )
        if created_delta:
            obj.created_at = obj.created_at - dt.timedelta(seconds=created_delta)
            obj.save(update_fields=["created_at"])
        return obj
    return _mk