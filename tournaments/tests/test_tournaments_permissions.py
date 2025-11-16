import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.http import HttpResponse
from django.utils import timezone
from tournaments.models import Tournament
from tournaments.permissions import staff_or_tadmin

User = get_user_model()

@pytest.mark.django_db
def test_staff_or_tadmin_forbidden_for_anonymous(client):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    url = reverse("tournaments:toggle_registration", args=[t.pk])
    resp = client.get(url)
    assert resp.status_code == 403

@pytest.mark.django_db
def test_staff_or_tadmin_allows_staff(client, django_user_model):
    staff = django_user_model.objects.create_user(
        username="staff", password="x", is_staff=True
    )
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    client.force_login(staff)
    url = reverse("tournaments:toggle_registration", args=[t.pk])
    resp = client.get(url)
    assert resp.status_code in (302, 303)

@pytest.mark.django_db
def test_staff_or_tadmin_allows_tournament_admin(client, django_user_model):
    user = django_user_model.objects.create_user(username="ta", password="x")
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    t.admins.add(user)
    client.force_login(user)
    url = reverse("tournaments:toggle_registration", args=[t.pk])
    resp = client.get(url)
    assert resp.status_code in (302, 303)

@pytest.mark.django_db
def test_staff_or_tadmin_forbidden_for_regular_user(client, django_user_model):
    user = django_user_model.objects.create_user(username="regular", password="x")
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    client.force_login(user)
    url = reverse("tournaments:toggle_registration", args=[t.pk])
    resp = client.get(url)
    assert resp.status_code == 403

def _ok_view(request, *args, **kwargs):
    return HttpResponse("ok")


@pytest.mark.django_db
def test_staff_or_tadmin_nonexistent_tournament_returns_403():
    rf = RequestFactory()
    user = User.objects.create_user(username="u1", password="x")
    req = rf.get("/toggle")
    req.user = user

    wrapped = staff_or_tadmin(_ok_view)
    resp = wrapped(req, pk=999999)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_staff_or_tadmin_allows_when_user_is_tournament_admin_direct():
    rf = RequestFactory()
    user = User.objects.create_user(username="ta2", password="x")
    t = Tournament.objects.create(name="Cup2", start_date=timezone.now())
    t.admins.add(user)

    req = rf.get("/toggle")
    req.user = user

    wrapped = staff_or_tadmin(_ok_view)
    resp = wrapped(req, pk=t.pk)
    assert resp.status_code == 200
    assert resp.content == b"ok"


@pytest.mark.django_db
def test_staff_or_tadmin_forbidden_when_not_tadmin_direct():
    rf = RequestFactory()
    user = User.objects.create_user(username="notadmin", password="x")
    t = Tournament.objects.create(name="Cup3", start_date=timezone.now())

    req = rf.get("/toggle")
    req.user = user

    wrapped = staff_or_tadmin(_ok_view)
    resp = wrapped(req, pk=t.pk)
    assert resp.status_code == 403

@pytest.mark.django_db
def test_staff_or_tadmin_missing_pk_returns_403():
    rf = RequestFactory()
    user = User.objects.create_user(username="u_missing_pk", password="x")
    req = rf.get("/toggle")
    req.user = user

    wrapped = staff_or_tadmin(_ok_view)
    resp = wrapped(req)
    assert resp.status_code == 403