import pytest
from django.urls import reverse
from django.utils import timezone
from tournaments.models import Tournament, TournamentTeam, Match
from teams.models import Team

@pytest.mark.django_db
def test_start_tournament_success_creates_bracket_and_runs(client, staff, make_team):
    # турнир «предстоящий» с 2+ командами
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="upcoming",
        registration_open=True,
    )
    a = make_team("Alpha", "A")
    b = make_team("Bravo", "B")
    TournamentTeam.objects.create(tournament=t, team=a)
    TournamentTeam.objects.create(tournament=t, team=b)

    client.force_login(staff)
    resp = client.get(reverse("tournaments:start", args=[t.pk]))
    # редирект на сетку
    assert resp.status_code in (302, 303)
    assert reverse("tournaments:bracket", args=[t.pk]) in resp.url

    t.refresh_from_db()
    assert t.status == "running"
    assert t.registration_open is False
    assert Match.objects.filter(tournament=t).exists()  # сетка создана

@pytest.mark.django_db
def test_start_tournament_requires_two_teams(client, staff, make_team):
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="upcoming",
        registration_open=True,
    )
    a = make_team("Alpha", "A")
    TournamentTeam.objects.create(tournament=t, team=a)  # только 1 команда

    client.force_login(staff)
    resp = client.get(reverse("tournaments:start", args=[t.pk]), follow=True)

    t.refresh_from_db()
    assert t.status == "upcoming"            # не запустился
    assert t.registration_open is True       # регистрация не закрылась
    # редирект на overview
    assert resp.redirect_chain
    assert reverse("tournaments:overview", args=[t.pk]) in resp.redirect_chain[-1][0]

@pytest.mark.django_db
def test_start_tournament_when_already_running_redirects_only(client, staff):
    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="running",
        registration_open=False,
    )
    client.force_login(staff)
    resp = client.get(reverse("tournaments:start", args=[t.pk]))
    assert resp.status_code in (302, 303)
    assert reverse("tournaments:bracket", args=[t.pk]) in resp.url
