import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from tournaments.models import Tournament

User = get_user_model()

@pytest.mark.django_db
def test_staff_or_tadmin_forbidden_for_anonymous(client):
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    url = reverse("tournaments:toggle_registration", args=[t.pk])
    resp = client.get(url)
    assert resp.status_code == 403  # HttpResponseForbidden для неавторизованных

@pytest.mark.django_db
def test_staff_or_tadmin_allows_staff(client, django_user_model):
    staff = django_user_model.objects.create_user(
        username="staff", password="x", is_staff=True
    )
    t = Tournament.objects.create(name="Cup", start_date=timezone.now())
    client.force_login(staff)
    url = reverse("tournaments:toggle_registration", args=[t.pk])
    resp = client.get(url)
    # вьюха редиректит на settings — важно, что не 403
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
