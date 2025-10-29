# tournaments/tests/test_views_register_team.py
import pytest
from django.urls import reverse
from django.utils import timezone
from tournaments.models import Tournament, TournamentTeam


@pytest.mark.django_db
def test_register_team_success_by_captain(client, make_user, make_team):
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(),
        status="upcoming", max_teams=8, registration_open=True
    )
    captain = make_user("cap_alpha")
    team = make_team(name="Alpha", tag="A", captain=captain)

    client.force_login(captain)
    url = reverse("tournaments:register_team", args=[t.pk, team.pk])
    resp = client.get(url)

    assert resp.status_code in (302, 303)
    assert TournamentTeam.objects.filter(tournament=t, team=team).exists()
    assert f"?joined={team.id}" in resp.url


@pytest.mark.django_db
def test_register_team_forbidden_if_not_captain(client, make_user, make_team):
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(),
        status="upcoming", max_teams=8, registration_open=True
    )
    captain = make_user("cap_bravo")
    stranger = make_user("stranger")
    team = make_team(name="Bravo", tag="B", captain=captain)

    client.force_login(stranger)
    url = reverse("tournaments:register_team", args=[t.pk, team.pk])
    resp = client.get(url)

    assert resp.status_code in (302, 303)
    assert not TournamentTeam.objects.filter(tournament=t, team=team).exists()


@pytest.mark.django_db
def test_register_team_forbidden_when_registration_closed(client, make_user, make_team):
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(),
        status="upcoming", max_teams=8, registration_open=False
    )
    captain = make_user("cap_charlie")
    team = make_team(name="Charlie", tag="C", captain=captain)

    client.force_login(captain)
    url = reverse("tournaments:register_team", args=[t.pk, team.pk])
    resp = client.get(url)

    assert resp.status_code in (302, 303)
    assert not TournamentTeam.objects.filter(tournament=t, team=team).exists()


@pytest.mark.django_db
def test_register_team_forbidden_when_no_slots_left(client, make_user, make_team):
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(),
        status="upcoming", max_teams=1, registration_open=True
    )
    cap1 = make_user("cap_delta")
    team1 = make_team(name="Delta", tag="D", captain=cap1)
    TournamentTeam.objects.create(tournament=t, team=team1)

    cap2 = make_user("cap_echo")
    team2 = make_team(name="Echo", tag="E", captain=cap2)

    client.force_login(cap2)
    url = reverse("tournaments:register_team", args=[t.pk, team2.pk])
    resp = client.get(url)

    assert resp.status_code in (302, 303)
    assert not TournamentTeam.objects.filter(tournament=t, team=team2).exists()
