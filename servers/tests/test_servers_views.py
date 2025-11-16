import re
import pytest
from django.urls import reverse
from servers import views


def test__mode_dict_structure_complete():
    d = views._mode_dict()
    expected_codes = [m[0] for m in views.MODES]
    assert set(d.keys()) == set(expected_codes)
    for code, info in d.items():
        assert info["code"] == code
        assert {"code", "title", "color", "capacity"} <= set(info.keys())
        assert isinstance(info["capacity"], int) and info["capacity"] > 0


def test__servers_for_generates_7_with_fields_and_caps():
    code = "dm"
    servers = views._servers_for(code)
    assert len(servers) == len(views.MAPS) == 7
    base_port = 27015
    for i, srv in enumerate(servers, start=1):
        assert {"num", "mode_code", "mode_name", "map",
                "players", "capacity", "ip", "thumb"} <= set(srv.keys())
        assert 0 < srv["players"] <= srv["capacity"]
        assert srv["ip"] == f"127.0.0.1:{base_port + i}"
        assert srv["thumb"].endswith(f"img/maps/{srv['map']}.jpg")


@pytest.mark.django_db
def test_servers_home_renders_and_totals(client):
    resp = client.get(reverse("servers:home"))
    assert resp.status_code == 200
    modes = resp.context["modes"]
    assert len(modes) == len(views.MODES) == 10
    for m in modes:
        total = sum(s["players"] for s in m["servers"])
        assert m["players_total"] == total
        assert len(m["servers"]) == len(views.MAPS) == 7


@pytest.mark.django_db
def test_mode_page_redirects_on_bad_mode(client):
    resp = client.get(reverse("servers:mode", args=["NOPE"]))
    assert resp.status_code in (302, 303)
    assert resp.url == reverse("servers:home")


@pytest.mark.django_db
@pytest.mark.parametrize("code,_title,_color,_cap", views.MODES)
def test_mode_page_ok_for_each_mode(client, code, _title, _color, _cap):
    resp = client.get(reverse("servers:mode", args=[code]))
    assert resp.status_code == 200
    ctx = resp.context
    assert ctx["active_mode"] == code
    assert ctx["mode"]["code"] == code
    assert ctx["mode_nav"] == views.MODES
    servers = ctx["servers"]
    assert len(servers) == len(views.MAPS) == 7
    for i, s in enumerate(servers, start=1):
        assert s["mode_code"] == code
        assert s["capacity"] == _cap
        assert s["map"] in views.MAPS
        assert re.match(r"^127\.0\.0\.1:\d{2,5}$", s["ip"])
