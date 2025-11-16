import pytest
from django.urls import reverse
from django.contrib import messages
from teams.models import Team

pytestmark = pytest.mark.django_db

def test_join_by_code_created_membership(logged_client, team, user):
    url = reverse("teams:join_by_code", kwargs={"code": team.invite_code})
    resp = logged_client.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("teams:team_detail", kwargs={"slug": team.slug})


def test_join_by_code_already_member_shows_info(captain_client, team):
    url = reverse("teams:join_by_code", kwargs={"code": team.invite_code})
    resp = captain_client.get(url)
    assert resp.status_code == 302 


def test_leave_team_captain_forbidden(captain_client, team):
    url = reverse("teams:leave_team", kwargs={"slug": team.slug})
    resp = captain_client.get(url)
    assert resp.status_code == 302


def test_leave_team_player_ok(logged_client, team, user):
    from teams.models import TeamMembership
    TeamMembership.objects.create(team=team, user=user, role="player")
    url = reverse("teams:leave_team", kwargs={"slug": team.slug})
    resp = logged_client.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("teams:my_teams")


def test_transfer_captain_forbidden_for_non_captain(logged_client, team):
    url = reverse("teams:transfer_captain", kwargs={"slug": team.slug, "user_id": 999999})
    resp = logged_client.get(url)
    assert resp.status_code == 302


def test_transfer_captain_ok(captain_client, team, user):
    from teams.models import TeamMembership
    TeamMembership.objects.create(team=team, user=user, role="player")
    url = reverse("teams:transfer_captain", kwargs={"slug": team.slug, "user_id": user.id})
    resp = captain_client.get(url)
    assert resp.status_code == 302
    team.refresh_from_db()
    assert team.captain_id == user.id


def test_remove_member_forbidden_for_non_captain(logged_client, team, user):
    url = reverse("teams:remove_member", kwargs={"slug": team.slug, "user_id": user.id})
    resp = logged_client.get(url)
    assert resp.status_code == 302


def test_remove_member_cannot_remove_captain(captain_client, team):
    url = reverse("teams:remove_member", kwargs={"slug": team.slug, "user_id": team.captain_id})
    resp = captain_client.get(url)
    assert resp.status_code == 302


def test_remove_member_ok(captain_client, team, user):
    from teams.models import TeamMembership
    TeamMembership.objects.create(team=team, user=user, role="player")
    url = reverse("teams:remove_member", kwargs={"slug": team.slug, "user_id": user.id})
    resp = captain_client.get(url)
    assert resp.status_code == 302
    assert not TeamMembership.objects.filter(team=team, user=user).exists()

def test_delete_team_requires_login(client, team):
    url = reverse("teams:delete_team", args=[team.slug])
    resp = client.get(url)
    assert resp.status_code in (302, 303)
    assert "login" in resp.headers.get("Location", "")


def test_delete_team_forbidden_for_non_captain(logged_client, team, user):
    url = reverse("teams:delete_team", args=[team.slug])
    resp = logged_client.post(url)
    assert resp.status_code == 403
    assert "Only captain can delete the team." in resp.content.decode()
    assert Team.objects.filter(pk=team.pk).exists()


def test_delete_team_method_not_allowed_for_get(captain_client, team):
    url = reverse("teams:delete_team", args=[team.slug])
    resp = captain_client.get(url)
    assert resp.status_code == 405
    assert Team.objects.filter(pk=team.pk).exists()


def test_delete_team_success_by_captain(captain_client, team):
    url = reverse("teams:delete_team", args=[team.slug])
    resp = captain_client.post(url)
    assert resp.status_code in (302, 303)
    assert reverse("teams:my_teams") in resp.headers.get("Location", "")
    storage = list(messages.get_messages(resp.wsgi_request))
    assert any("Team deleted" in str(m) for m in storage)
    assert not Team.objects.filter(pk=team.pk).exists()