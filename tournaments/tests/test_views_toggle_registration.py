import pytest
from django.urls import reverse
from django.utils import timezone
from tournaments.models import Tournament

@pytest.mark.django_db
def test_toggle_registration_upcoming_ok(client, staff):
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(),
        status="upcoming", registration_open=True
    )
    client.force_login(staff)
    resp = client.get(reverse("tournaments:toggle_registration", args=[t.pk]))
    assert resp.status_code in (302, 303)
    t.refresh_from_db()
    assert t.registration_open is False  # переключилось

@pytest.mark.django_db
def test_toggle_registration_not_allowed_when_running(client, staff):
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(),
        status="running", registration_open=False
    )
    client.force_login(staff)
    resp = client.get(reverse("tournaments:toggle_registration", args=[t.pk]), follow=True)
    t.refresh_from_db()
    assert t.registration_open is False  # не изменилось
    # редирект на settings (как во вьюхе)
    assert resp.redirect_chain
