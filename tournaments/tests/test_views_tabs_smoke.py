import pytest
from django.urls import reverse
from django.utils import timezone
from tournaments.models import Tournament

@pytest.mark.django_db
def test_all_tabs_return_200_for_logged_user(client, make_user):
    user = make_user("viewer")
    client.force_login(user)

    t = Tournament.objects.create(
        name="Cup",
        start_date=timezone.now(),
        status="upcoming",
        max_teams=8,
        registration_open=True,
    )

    urls = [
        reverse("tournaments:overview", args=[t.pk]),
        reverse("tournaments:bracket",  args=[t.pk]),
        reverse("tournaments:matches",  args=[t.pk]),
        reverse("tournaments:teams",    args=[t.pk]),
        reverse("tournaments:results",  args=[t.pk]),
    ]

    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 200
