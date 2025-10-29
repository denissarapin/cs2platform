import pytest
from django.utils import timezone
from django.urls import reverse

from tournaments.models import Tournament, Match
from teams.models import Team

# 1) Список турниров
@pytest.mark.django_db
def test_api_tournament_list(client):
    t1 = Tournament.objects.create(name="Alpha Cup", start_date=timezone.now())
    t2 = Tournament.objects.create(name="Beta Cup", start_date=timezone.now())
    url = reverse("tournaments:api_tournament_list")

    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    # ожидаем список и что в нём есть наши турниры по именам
    names = {item["name"] for item in data}
    assert {"Alpha Cup", "Beta Cup"} <= names

@pytest.mark.django_db
def test_api_tournament_detail_includes_matches(client, make_team):
    t = Tournament.objects.create(name="Detail Cup", start_date=timezone.now())
    a = make_team("Team A", tag="TMA")
    b = make_team("Team B", tag="TMB")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, round=1, status="scheduled")

    url = reverse("tournaments:api_tournament_detail", args=[t.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == t.id
    assert data["name"] == "Detail Cup"
    matches = data.get("matches", [])
    assert len(matches) == 1
    assert matches[0]["id"] == m.id
    assert matches[0]["team_a"]["name"] == a.name
    assert matches[0]["team_b"]["name"] == b.name

# 3) POST отчёт о матче
@pytest.mark.django_db
def test_api_report_match_success(client, staff, make_team):
    t = Tournament.objects.create(name="Report Cup", start_date=timezone.now())
    a = make_team("Alpha")
    b = make_team("Bravo")
    m = Match.objects.create(tournament=t, team_a=a, team_b=b, round=1, status="scheduled")

    client.force_login(staff)
    url = reverse("tournaments:api_report_match", args=[t.pk])
    payload = {"match_id": m.id, "score_a": 16, "score_b": 10}

    resp = client.post(url, data=payload, content_type="application/json")
    assert resp.status_code in (200, 201, 204)  # зависит от реализации Response
    m.refresh_from_db()
    assert m.status == "finished"
    assert m.winner_id == a.id
