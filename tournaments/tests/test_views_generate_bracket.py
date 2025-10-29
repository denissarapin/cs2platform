import pytest
from django.urls import reverse
from django.utils import timezone
from tournaments.models import Tournament, TournamentTeam
from teams.models import Team

@pytest.mark.django_db
def test_generate_tournament_bracket_creates_matches_and_redirects(client, staff, make_team):
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(), status="upcoming"
    )
    # две команды, чтобы сетка точно создалась
    a = make_team(name="A", tag="A")
    b = make_team(name="B", tag="B")
    TournamentTeam.objects.create(tournament=t, team=a)
    TournamentTeam.objects.create(tournament=t, team=b)

    client.force_login(staff)
    url = reverse("tournaments:generate_bracket", args=[t.pk])
    resp = client.get(url)

    # редирект на страницу сетки
    assert resp.status_code in (302, 303)
    assert reverse("tournaments:bracket", args=[t.pk]) in resp.url

    # матчи созданы
    assert t.matches.exists()
