# tournaments/tests/test_views_report.py
import pytest
from django.urls import reverse
from django.utils import timezone

from tournaments.models import Tournament, Match, TournamentTeam
from teams.models import Team


def _make_match(db, make_team, t: Tournament):
    """Вспомогалка: создать 2 команды, зарегистрировать их и сделать матч."""
    a = make_team(name="TeamA", tag="A")
    b = make_team(name="TeamB", tag="B")
    TournamentTeam.objects.create(tournament=t, team=a)
    TournamentTeam.objects.create(tournament=t, team=b)
    m = Match.objects.create(tournament=t, round=1, team_a=a, team_b=b, status="scheduled")
    return a, b, m


@pytest.mark.django_db
def test_report_match_result_valid(client, staff, make_team):
    # given
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a, b, m = _make_match(db=True, make_team=make_team, t=t)
    client.force_login(staff)

    # when
    url = reverse("tournaments:report_match", args=[t.pk, m.pk])
    resp = client.post(url, {"score_a": "16", "score_b": "10"})

    # then (редирект и матч завершён, winner = team_a)
    assert resp.status_code in (302, 303)
    m.refresh_from_db()
    assert m.status == "finished"
    assert m.score_a == 16 and m.score_b == 10
    assert m.winner_id == a.id


@pytest.mark.django_db
def test_report_match_result_bad_format_keeps_scheduled(client, staff, make_team):
    # given
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a, b, m = _make_match(db=True, make_team=make_team, t=t)
    client.force_login(staff)

    # when (нечисловой счёт)
    url = reverse("tournaments:report_match", args=[t.pk, m.pk])
    resp = client.post(url, {"score_a": "abc", "score_b": "10"})

    # then: редирект, матч не изменился и остался scheduled
    assert resp.status_code in (302, 303)
    m.refresh_from_db()
    assert m.status == "scheduled"
    assert m.score_a == 0 and m.score_b == 0
    assert m.winner_id is None


@pytest.mark.django_db
def test_report_match_result_htmx_204_and_trigger(client, staff, make_team):
    # given
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    a, b, m = _make_match(db=True, make_team=make_team, t=t)
    client.force_login(staff)

    # when: HTMX-запрос
    url = reverse("tournaments:report_match", args=[t.pk, m.pk])
    resp = client.post(
        url,
        {"score_a": "16", "score_b": "5"},
        HTTP_HX_REQUEST="true",   # важный заголовок
    )

    # then: 204 + заголовок HX-Trigger, и матч завершён
    assert resp.status_code == 204
    assert resp.headers.get("HX-Trigger") == "match-updated"
    m.refresh_from_db()
    assert m.status == "finished"
    assert m.winner_id == a.id
