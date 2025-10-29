import pytest
from django.urls import reverse, resolve

@pytest.mark.django_db
def test_home_url_resolves():
    name = "home"
    url = reverse(name)
    match = resolve(url)
    assert match.url_name == name
