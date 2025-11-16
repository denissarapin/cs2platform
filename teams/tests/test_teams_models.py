import pytest
from teams.models import TeamInvite, TeamMembership

pytestmark = pytest.mark.django_db


def test_teammembership_str_includes_user_team_role(team, user):
    m = TeamMembership.objects.create(team=team, user=user, role="player")
    s = str(m)
    assert user.username in s
    assert team.tag in s or team.name in s
    assert "(player)" in s


def test_teaminvite_str_and_is_active(invite_factory, user):
    inv = invite_factory(user, status=TeamInvite.Status.PENDING)
    s = str(inv)
    assert "Invite[" in s
    assert user.username in s
    assert inv.is_active is True
    inv.status = TeamInvite.Status.ACCEPTED
    inv.save(update_fields=["status"])
    assert inv.is_active is False


def test_accept_creates_membership_when_absent(team, user, invite_factory):
    inv = invite_factory(user, status=TeamInvite.Status.PENDING)
    assert not TeamMembership.objects.filter(team=team, user=user).exists()

    inv.accept()

    assert TeamMembership.objects.filter(team=team, user=user).exists()
    inv.refresh_from_db()
    assert inv.status == TeamInvite.Status.ACCEPTED
    assert inv.responded_at is not None


def test_accept_does_not_duplicate_when_member_exists(team, user, invite_factory):
    TeamMembership.objects.create(team=team, user=user, role="player")
    inv = invite_factory(user, status=TeamInvite.Status.PENDING)

    before = TeamMembership.objects.filter(team=team, user=user).count()
    inv.accept()
    after = TeamMembership.objects.filter(team=team, user=user).count()

    assert after == before
    inv.refresh_from_db()
    assert inv.status == TeamInvite.Status.ACCEPTED
