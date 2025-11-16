import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from teams.views import _is_htmx

pytestmark = pytest.mark.django_db


def test_is_htmx_true_false(rf):
    req = rf.get("/")
    assert _is_htmx(req) is False
    req = rf.get("/", HTTP_HX_REQUEST="true")
    assert _is_htmx(req) is True


def test_my_teams_requires_login(client):
    url = reverse("teams:my_teams")
    resp = client.get(url)
    assert resp.status_code == 302


def test_my_teams_ok(logged_client, user, team, invite_factory):
    invite_factory(invited_user=user)
    url = reverse("teams:my_teams")
    resp = logged_client.get(url)
    assert resp.status_code == 200


def test_team_detail_ok(client, team):
    url = reverse("teams:team_detail", kwargs={"slug": team.slug})
    resp = client.get(url)
    assert resp.status_code == 200


def test_team_create_get(captain_client):
    url = reverse("teams:team_create")
    resp = captain_client.get(url)
    assert resp.status_code == 200


def test_team_create_post_invalid(captain_client):
    with patch("teams.views.TeamCreateForm") as Form:
        form = Form.return_value
        form.is_valid.return_value = False
        url = reverse("teams:team_create")
        resp = captain_client.post(url, data={})
        assert resp.status_code == 200
        form.is_valid.assert_called_once()


def test_team_create_post_valid_redirect_creates_membership_and_message(captain_client):
    dummy_team = MagicMock()
    dummy_team.slug = "new-team"
    with patch("teams.views.TeamCreateForm") as Form, \
         patch("teams.views.TeamMembership.objects.create") as create_mem:
        form = Form.return_value
        form.is_valid.return_value = True
        form.save.return_value = dummy_team
        url = reverse("teams:team_create")
        resp = captain_client.post(url, data={"name": "X"})
        assert resp.status_code == 302
        assert resp.url == reverse("teams:team_detail", kwargs={"slug": "new-team"})
        assert create_mem.called


def test_user_search_forbidden_for_non_captain(logged_client, team):
    url = reverse("teams:user_search", kwargs={"slug": team.slug})
    resp = logged_client.get(url)
    assert resp.status_code == 403


def test_user_search_default_suggestions(captain_client, team, user, another_user, third_user):
    url = reverse("teams:user_search", kwargs={"slug": team.slug})
    resp = captain_client.get(url)
    assert resp.status_code == 200


def test_user_search_with_query(captain_client, team, another_user):
    url = reverse("teams:user_search", kwargs={"slug": team.slug})
    resp = captain_client.get(url + "?q=u")
    assert resp.status_code == 200
