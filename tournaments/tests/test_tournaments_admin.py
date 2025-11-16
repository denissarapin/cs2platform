import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model

from tournaments.admin import TournamentAdmin, TournamentTeamInline
from tournaments.models import Tournament, TournamentTeam
from teams.models import Team
from django.utils import timezone


@pytest.mark.django_db
def test_tournament_admin_counts_and_labels(make_team):
    User = get_user_model()

    t = Tournament.objects.create(name="Admin Cup", start_date=timezone.now())
    u1 = User.objects.create_user(username="u1")
    u2 = User.objects.create_user(username="u2")
    t.admins.add(u1, u2)
    team_a = make_team("Alpha", tag="ALP")
    team_b = make_team("Bravo", tag="BRV")
    TournamentTeam.objects.create(tournament=t, team=team_a)
    TournamentTeam.objects.create(tournament=t, team=team_b)

    admin_site = AdminSite()
    adm = TournamentAdmin(Tournament, admin_site)

    assert adm.admins_count(t) == 2
    assert getattr(TournamentAdmin.admins_count, "short_description", "") == "Admins"

    assert adm.participants_count(t) == 2
    assert getattr(TournamentAdmin.participants_count, "short_description", "") == "Teams"
def test_tournament_admin_config_shape():
    admin_site = AdminSite()
    adm = TournamentAdmin(Tournament, admin_site)

    assert "admins_count" in adm.list_display
    assert "participants_count" in adm.list_display
    assert "name" in adm.list_display
    assert "status" in adm.list_filter
    assert "registration_open" in adm.list_filter
    assert "admins" in adm.list_filter
    assert "name" in adm.search_fields
    assert TournamentTeamInline in adm.inlines
    assert "admins" in adm.filter_horizontal
