import uuid
import pytest
from unittest.mock import patch
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponse

pytestmark = pytest.mark.django_db


def test_outgoing_invites_forbidden_for_non_captain(logged_client, team):
    url = reverse("teams:outgoing_invites", kwargs={"slug": team.slug})
    resp = logged_client.get(url)
    assert resp.status_code == 403


def test_outgoing_invites_ok(captain_client, team):
    url = reverse("teams:outgoing_invites", kwargs={"slug": team.slug})
    resp = captain_client.get(url)
    assert resp.status_code == 200


def test_send_invite_method_not_allowed(captain_client, team):
    url = reverse("teams:send_invite", kwargs={"slug": team.slug})
    resp = captain_client.get(url)
    assert resp.status_code == 405


def test_send_invite_forbidden_for_non_captain(logged_client, team, another_user):
    url = reverse("teams:send_invite", kwargs={"slug": team.slug})
    resp = logged_client.post(url, data={"user_id": another_user.id})
    assert resp.status_code == 403


def test_send_invite_bad_user_id(captain_client, team):
    url = reverse("teams:send_invite", kwargs={"slug": team.slug})
    resp = captain_client.post(url, data={"user_id": "abc"})
    assert resp.status_code == 400


def test_send_invite_already_member_returns_204(captain_client, team, another_user):
    from teams.models import TeamMembership
    TeamMembership.objects.create(team=team, user=another_user, role="player")
    url = reverse("teams:send_invite", kwargs={"slug": team.slug})
    resp = captain_client.post(url, data={"user_id": another_user.id})
    assert resp.status_code == 204


def test_send_invite_created_ok(captain_client, team, another_user):
    url = reverse("teams:send_invite", kwargs={"slug": team.slug})
    resp = captain_client.post(url, data={"user_id": another_user.id})
    assert resp.status_code == 200


def test_send_invite_reopen_from_non_pending(captain_client, team, another_user, invite_factory):
    from teams.models import TeamInvite
    inv = invite_factory(invited_user=another_user, status=TeamInvite.Status.DECLINED)
    url = reverse("teams:send_invite", kwargs={"slug": team.slug})
    before = timezone.now()
    resp = captain_client.post(url, data={"user_id": another_user.id})
    assert resp.status_code == 200
    inv.refresh_from_db()
    assert inv.status == TeamInvite.Status.PENDING
    assert inv.invited_by.username == "cap"
    assert inv.responded_at is None
    assert inv.created_at >= before


def test_cancel_invite_method_not_allowed(captain_client, team, invite_factory, another_user):
    inv = invite_factory(another_user)
    url = reverse("teams:cancel_invite", kwargs={"slug": team.slug, "invite_id": inv.id})
    resp = captain_client.get(url)
    assert resp.status_code == 405


def test_cancel_invite_forbidden_non_captain(logged_client, team, invite_factory, another_user):
    inv = invite_factory(another_user)
    url = reverse("teams:cancel_invite", kwargs={"slug": team.slug, "invite_id": inv.id})
    resp = logged_client.post(url)
    assert resp.status_code == 403


def test_cancel_invite_ok(captain_client, team, invite_factory, another_user):
    inv = invite_factory(another_user)
    url = reverse("teams:cancel_invite", kwargs={"slug": team.slug, "invite_id": inv.id})
    resp = captain_client.post(url)
    assert resp.status_code == 200


def test_invites_count(logged_client, user, team, invite_factory):
    invite_factory(user)
    url = reverse("teams:invites_count")
    resp = logged_client.get(url)
    assert resp.status_code == 200


def test_invites_panel(logged_client, user, team, invite_factory):
    invite_factory(user)
    url = reverse("teams:invites_panel")
    resp = logged_client.get(url)
    assert resp.status_code == 200


def test_accept_invite_forbidden_if_not_for_you(logged_client, captain_user, team, invite_factory):
    inv = invite_factory(captain_user, code=uuid.uuid4())
    url = reverse("teams:accept_invite", kwargs={"code": inv.code})
    resp = logged_client.get(url)
    assert resp.status_code == 403


def test_accept_invite_already_processed_non_htmx(logged_client, user, team, invite_factory):
    from teams.models import TeamInvite
    inv = invite_factory(user, code=uuid.uuid4(), status=TeamInvite.Status.ACCEPTED)
    url = reverse("teams:accept_invite", kwargs={"code": inv.code})
    resp = logged_client.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("teams:my_teams")


def test_accept_invite_pending_non_htmx_joins_team(logged_client, user, team, invite_factory):
    from teams.models import TeamMembership, TeamInvite
    inv = invite_factory(user, code=uuid.uuid4(), status=TeamInvite.Status.PENDING)
    url = reverse("teams:accept_invite", kwargs={"code": inv.code})
    resp = logged_client.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("teams:team_detail", kwargs={"slug": team.slug})
    assert TeamMembership.objects.filter(team=team, user=user).exists()


def test_accept_invite_already_processed_htmx_returns_panel(logged_client, user, team, invite_factory):
    from teams.models import TeamInvite
    class DummyPanel(HttpResponse):
        def __init__(self): super().__init__(b"PANEL")
        def render(self): return self
    inv = invite_factory(user, code=uuid.uuid4(), status=TeamInvite.Status.DECLINED)
    with patch("teams.views.invites_panel", return_value=DummyPanel()):
        url = reverse("teams:accept_invite", kwargs={"code": inv.code})
        resp = logged_client.get(url, HTTP_HX_REQUEST="true")
        assert resp.status_code == 200


def test_accept_invite_pending_htmx_appends_oob(logged_client, user, team, invite_factory):
    from teams.models import TeamInvite
    class DummyPanel(HttpResponse):
        def __init__(self): super().__init__(b"PANEL")
        def render(self): return self
    inv = invite_factory(user, code=uuid.uuid4(), status=TeamInvite.Status.PENDING)
    with patch("teams.views.invites_panel", return_value=DummyPanel()):
        url = reverse("teams:accept_invite", kwargs={"code": inv.code})
        resp = logged_client.get(url, HTTP_HX_REQUEST="true")
        assert resp.status_code == 200
        assert b"PANEL" in resp.content
        assert (
            b"notif_count" in resp.content
            or b'notifCount' in resp.content
            or b'id="notifCount"' in resp.content
        )


def test_decline_invite_forbidden_if_not_for_you(logged_client, captain_user, team, invite_factory):
    inv = invite_factory(captain_user, code=uuid.uuid4())
    url = reverse("teams:decline_invite", kwargs={"code": inv.code})
    resp = logged_client.get(url)
    assert resp.status_code == 403


def test_decline_invite_pending_non_htmx(logged_client, user, team, invite_factory):
    from teams.models import TeamInvite
    inv = invite_factory(user, code=uuid.uuid4(), status=TeamInvite.Status.PENDING)
    url = reverse("teams:decline_invite", kwargs={"code": inv.code})
    resp = logged_client.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("teams:my_teams")


def test_decline_invite_pending_htmx(logged_client, user, team, invite_factory):
    from teams.models import TeamInvite
    class DummyPanel(HttpResponse):
        def __init__(self): super().__init__(b"PANEL")
        def render(self): return self
    inv = invite_factory(user, code=uuid.uuid4(), status=TeamInvite.Status.PENDING)
    with patch("teams.views.invites_panel", return_value=DummyPanel()):
        url = reverse("teams:decline_invite", kwargs={"code": inv.code})
        resp = logged_client.get(url, HTTP_HX_REQUEST="true")
        assert resp.status_code == 200

def test_send_invite_with_query_filters_candidates(captain_client, team, another_user):
    from django.urls import reverse
    url = reverse("teams:send_invite", kwargs={"slug": team.slug})
    resp = captain_client.post(url, data={"user_id": another_user.id, "q": "u"})
    assert resp.status_code == 200

def test_decline_invite_non_pending_non_htmx_redirects(logged_client, user, team, invite_factory):
    from django.urls import reverse
    from teams.models import TeamInvite
    inv = invite_factory(user, status=TeamInvite.Status.ACCEPTED)
    url = reverse("teams:decline_invite", kwargs={"code": inv.code})
    resp = logged_client.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("teams:my_teams")