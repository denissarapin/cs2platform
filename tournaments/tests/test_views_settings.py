import pytest
from django.urls import reverse
from django.utils import timezone
from tournaments.models import Tournament

HTML_DT = "%Y-%m-%d %H:%M"

@pytest.mark.django_db
def test_settings_forbidden_without_permissions(client, make_user):
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(), status="upcoming"
    )
    user = make_user("plain_user")
    client.force_login(user)

    resp = client.get(reverse("tournaments:settings", args=[t.pk]))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_settings_allowed_for_staff_and_updates_fields(client, staff):
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(), status="upcoming",
        max_teams=8, registration_open=True
    )
    client.force_login(staff)

    url = reverse("tournaments:settings", args=[t.pk])
    # GET доступен
    resp = client.get(url)
    assert resp.status_code == 200

    # POST меняем max_teams и registration_open
    new_start = timezone.now().replace(second=0, microsecond=0)
    post_data = {
        "max_teams": 32,
        "registration_open": "",         # снять чекбокс
        "status": "upcoming",
        "start_date": new_start.strftime(HTML_DT),
        "end_date": "",                  # пусто — ок
    }
    resp = client.post(url, post_data, follow=True)
    assert resp.status_code in (200, 302, 303)

    t.refresh_from_db()
    assert t.max_teams == 32
    assert t.registration_open is False
    # дата сохранится (погрешность по секундам исключили выше)
    assert t.start_date.strftime(HTML_DT) == new_start.strftime(HTML_DT)


@pytest.mark.django_db
def test_settings_allowed_for_tournament_admin(client, make_user):
    tadmin = make_user("tadmin")
    t = Tournament.objects.create(
        name="Cup", start_date=timezone.now(), status="upcoming"
    )
    t.admins.add(tadmin)

    client.force_login(tadmin)
    resp = client.get(reverse("tournaments:settings", args=[t.pk]))
    assert resp.status_code == 200
