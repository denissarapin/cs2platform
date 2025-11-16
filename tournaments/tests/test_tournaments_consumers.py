import json
import types
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio

class DummyChannelLayer:
    def __init__(self):
        self.added = []
        self.discarded = []
        self.sent = []
    async def group_add(self, name, channel_name):
        self.added.append((name, channel_name))
    async def group_discard(self, name, channel_name):
        self.discarded.append((name, channel_name))
    async def group_send(self, name, message):
        self.sent.append((name, message))

class FakeMapBans:
    def __init__(self, count=0, bans=None):
        self._count = count
        self._bans = bans or []
    def count(self):
        return self._count
    def select_related(self, *args, **kwargs):
        return self
    def order_by(self, *args, **kwargs):
        return self._bans

def make_fake_match(
    tournament="T",
    team_a=None,
    team_b=None,
    final_map_code=None,
    auto_ban_changed=False,
    ban_ok=True,
    ban_count=0,
    bans=None,
):
    team_a = team_a if team_a is not None else SimpleNamespace(id=1, captain_id=10)
    team_b = team_b if team_b is not None else SimpleNamespace(id=2, captain_id=20)
    fake = SimpleNamespace()
    fake.tournament = tournament
    fake.team_a = team_a
    fake.team_b = team_b
    fake.final_map_code = final_map_code
    fake.auto_ban_if_expired = MagicMock(return_value=auto_ban_changed)
    fake.ban_map = MagicMock(return_value=ban_ok)
    fake.map_bans = FakeMapBans(count=ban_count, bans=bans or [])
    return fake


@pytest.fixture
def channel_layer():
    return DummyChannelLayer()


@pytest.fixture
def scope_base():
    return {"type": "websocket", "url_route": {"kwargs": {"tournament_id": "1"}}}

import importlib
consumers = importlib.import_module("tournaments.consumers") 


async def test_bracket_consumer_connect_disconnect_and_update(channel_layer, scope_base, monkeypatch):
    scope = {**scope_base}
    consumer = consumers.BracketConsumer(scope=scope)
    consumer.scope = scope
    consumer.channel_layer = channel_layer
    consumer.channel_name = "ch123"

    consumer.accept = AsyncMock()
    consumer.send = AsyncMock()

    fake_match = make_fake_match()
    monkeypatch.setattr(consumer, "get_match", AsyncMock(return_value=fake_match))

    with patch("tournaments.consumers.render_to_string", return_value="<div>html</div>") as rts:
        await consumer.connect()
        assert ("tournament_1", "ch123") in channel_layer.added
        consumer.group_name = f"tournament_{scope['url_route']['kwargs']['tournament_id']}"
        await consumer.bracket_update({"match_id": 777})
        consumer.send.assert_awaited()
        payload = json.loads(consumer.send.call_args.kwargs["text_data"])
        assert payload["type"] == "bracket_update"
        assert payload["match_id"] == 777
        assert payload["html"] == "<div>html</div>"
        rts.assert_called()
        await consumer.disconnect(1000)
        assert ("tournament_1", "ch123") in channel_layer.discarded


async def test_bracket_consumer_get_match_sync_to_async(monkeypatch):
    fake_get_called = {"ok": False}
    class _Sel:
        def get(self, pk):
            fake_get_called["ok"] = (pk == 5)
            return "MATCH"
    class _Mgr:
        def select_related(self, *args, **kwargs):
            return _Sel()
    class _Match:
        objects = _Mgr()
    monkeypatch.setattr(consumers, "Match", _Match)
    got = await consumers.BracketConsumer(None).get_match(5)
    assert got == "MATCH"
    assert fake_get_called["ok"] is True

async def test_matches_consumer_flow(channel_layer, scope_base, capsys):
    scope = {**scope_base}
    consumer = consumers.MatchesConsumer(scope=scope)
    consumer.scope = scope  
    consumer.channel_layer = channel_layer
    consumer.channel_name = "ch456"
    consumer.accept = AsyncMock()
    consumer.send = AsyncMock()

    await consumer.connect()
    assert ("tournament_matches_1", "ch456") in channel_layer.added

    await consumer.matches_update({"action": "created", "message": "ok"})
    payload = json.loads(consumer.send.call_args.kwargs["text_data"])
    assert payload == {"type": "matches_update", "action": "created", "message": "ok"}

    await consumer.disconnect(1000)
    assert ("tournament_matches_1", "ch456") in channel_layer.discarded

def _make_scope_for_match(t_id=1, m_id=42, user=None):
    return {
        "type": "websocket",
        "url_route": {"kwargs": {"tournament_id": str(t_id), "match_id": str(m_id)}},
        "user": user or SimpleNamespace(is_authenticated=False, id=None, is_staff=False),
    }


async def _setup_match_consumer(monkeypatch, channel_layer, scope):
    c = consumers.MatchConsumer(scope=scope)
    c.scope = scope
    c.channel_layer = channel_layer
    c.channel_name = "ch789"
    c.accept = AsyncMock()
    c.send = AsyncMock()
    fake_match = make_fake_match()
    monkeypatch.setattr(c, "_get_match", AsyncMock(return_value=fake_match))
    monkeypatch.setattr(c, "_ban_count", AsyncMock(side_effect=lambda m: m.map_bans.count()))
    monkeypatch.setattr(c, "_get_bans", AsyncMock(side_effect=lambda m: list(m.map_bans.order_by("order"))))
    await c.connect()

    return c, fake_match


async def test_match_consumer_connect_disconnect(channel_layer):
    scope = _make_scope_for_match()
    c = consumers.MatchConsumer(scope=scope)
    c.scope = scope
    c.channel_layer = channel_layer
    c.channel_name = "ch789"
    c.accept = AsyncMock()

    await c.connect()
    assert ("match_42", "ch789") in channel_layer.added
    await c.disconnect(1000)
    assert ("match_42", "ch789") in channel_layer.discarded


async def test_match_consumer_receive_bad_json_is_ignored(monkeypatch, channel_layer):
    c, _ = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match())
    await c.receive("not a json")  
    c.send.assert_not_called()


async def test_match_consumer_receive_unknown_type_ignored(monkeypatch, channel_layer):
    c, _ = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match())
    await c.receive(json.dumps({"type": "something"}))
    c.send.assert_not_called()


async def test_match_consumer_heartbeat_no_change(monkeypatch, channel_layer):
    c, match = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match())
    match.auto_ban_if_expired.return_value = False
    await c.receive(json.dumps({"type": "heartbeat"}))
    assert channel_layer.sent == []


async def test_match_consumer_heartbeat_with_change_broadcast(monkeypatch, channel_layer):
    c, match = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match())
    match.auto_ban_if_expired.return_value = True

    with patch("tournaments.consumers.render_to_string", return_value="<x/>"), \
         patch("tournaments.consumers.get_available_maps", return_value=["de_inferno", "de_mirage"]):
        await c.receive(json.dumps({"type": "heartbeat"}))
        assert channel_layer.sent
        name, message = channel_layer.sent[-1]
        assert name == "match_42"
        assert message["type"] == "match_update"


async def test_match_consumer_ban_map_no_map_ignored(monkeypatch, channel_layer):
    c, _ = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match())
    await c.receive(json.dumps({"type": "ban_map"}))
    c.send.assert_not_called()


async def test_match_consumer_ban_map_permission_denied(monkeypatch, channel_layer):
    team_a = SimpleNamespace(id=1, captain_id=10)
    team_b = SimpleNamespace(id=2, captain_id=20)
    c, match = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match(
        user=SimpleNamespace(is_authenticated=True, id=999, is_staff=False)
    ))
    match.team_a, match.team_b = team_a, team_b
    match.map_bans = FakeMapBans(count=0)
    await c.receive(json.dumps({"type": "ban_map", "map_name": "de_mirage"}))
    c.send.assert_awaited()
    payload = json.loads(c.send.call_args.kwargs["text_data"])
    assert payload["type"] == "error"


async def test_match_consumer_ban_map_no_current_team(monkeypatch, channel_layer):
    c, match = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match(
        user=SimpleNamespace(is_authenticated=True, id=10, is_staff=False)
    ))
    match.team_a = None
    match.team_b = None
    match.map_bans = FakeMapBans(count=0)

    await c.receive(json.dumps({"type": "ban_map", "map_name": "de_nuke"}))
    payload = json.loads(c.send.call_args.kwargs["text_data"])
    assert payload["type"] == "error"


async def test_match_consumer_ban_map_bad_ok_false(monkeypatch, channel_layer):
    c, match = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match(
        user=SimpleNamespace(is_authenticated=True, id=10, is_staff=False)
    ))
    match.team_a.captain_id = 10
    match.map_bans = FakeMapBans(count=0)
    match.ban_map.return_value = False

    await c.receive(json.dumps({"type": "ban_map", "map_name": "de_ancient"}))
    payload = json.loads(c.send.call_args.kwargs["text_data"])
    assert payload["type"] == "error"
    assert "This map is no longer available for banning or it is not your turn" in payload["message"]


async def test_match_consumer_ban_map_success_broadcast(monkeypatch, channel_layer):
    user = SimpleNamespace(is_authenticated=True, id=10, is_staff=False)
    c, match = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match(user=user))
    match.team_a.captain_id = 10
    match.map_bans = FakeMapBans(count=0)
    match.ban_map.return_value = True

    with patch("tournaments.consumers.render_to_string", return_value="<ok/>"), \
         patch("tournaments.consumers.get_available_maps", return_value=["de_mirage", "de_overpass"]):
        await c.receive(json.dumps({"type": "ban_map", "map_name": "de_overpass"}))
        assert channel_layer.sent, "ожидали broadcast после удачного бана"
        last = channel_layer.sent[-1][1]
        assert last["type"] == "match_update"


async def test_match_consumer_broadcast_final_map_from_code(monkeypatch, channel_layer):
    c, match = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match())
    match.final_map_code = "de_cbble"
    match.map_bans = FakeMapBans(count=1)
    monkeypatch.setattr(consumers, "MAP_POOL", (("de_cbble", "Cobblestone"),))
    with patch("tournaments.consumers.render_to_string", return_value="<X/>") as rts, \
         patch("tournaments.consumers.get_available_maps", return_value=["de_cbble", "de_dust2"]):
        await c._broadcast_update()
        assert channel_layer.sent[-1][1]["type"] == "match_update"
        assert rts.call_count >= 2


async def test_match_consumer_broadcast_final_map_when_one_left(monkeypatch, channel_layer):
    c, match = await _setup_match_consumer(monkeypatch, channel_layer, _make_scope_for_match())
    match.final_map_code = None
    match.map_bans = FakeMapBans(count=6)
    monkeypatch.setattr(consumers, "MAP_POOL", (("de_train", "Train"),))
    with patch("tournaments.consumers.render_to_string", return_value="<Y/>") as rts, \
         patch("tournaments.consumers.get_available_maps", return_value=["de_train"]):
        await c._broadcast_update()
        sent = channel_layer.sent[-1][1]
        assert sent["type"] == "match_update"
        assert sent["show_veto_btn"] is True
        assert rts.call_count >= 2


async def test_match_consumer_match_update_sends(channel_layer):
    c = consumers.MatchConsumer(scope=_make_scope_for_match())
    c.channel_layer = channel_layer
    c.channel_name = "ch"
    c.send = AsyncMock()

    await c.match_update({"html": "<h1/>", "veto_html": "<v/>", "show_veto_btn": False})
    payload = json.loads(c.send.call_args.kwargs["text_data"])
    assert payload["type"] == "match_update"
    assert payload["html"] == "<h1/>"
    assert payload["veto_html"] == "<v/>"
    assert payload["show_veto_btn"] is False

async def test_match_consumer__get_match_hits_orm(monkeypatch):
    called = {"pk": None}

    class _Sel:
        def get(self, pk):
            called["pk"] = pk
            return "MATCH_OBJ"

    class _Mgr:
        def select_related(self, *args, **kwargs):
            assert "tournament" in args or "tournament" in kwargs.get("fields", ())
            return _Sel()

    class _Match:
        objects = _Mgr()

    monkeypatch.setattr(consumers, "Match", _Match)

    c = consumers.MatchConsumer(scope=_make_scope_for_match())
    c.match_id = 99 

    got = await c._get_match()
    assert got == "MATCH_OBJ"
    assert called["pk"] == 99


async def test_match_consumer__ban_count_counts():
    fake_match = SimpleNamespace(map_bans=FakeMapBans(count=3))
    c = consumers.MatchConsumer(scope=_make_scope_for_match())
    assert await c._ban_count(fake_match) == 3


async def test_match_consumer__get_bans_returns_list():
    expected = ["b1", "b2"]
    class _Bans(FakeMapBans):
        def select_related(self, *args, **kwargs):
            return self
        def order_by(self, *args, **kwargs):
            return expected

    fake_match = SimpleNamespace(map_bans=_Bans(count=2))
    c = consumers.MatchConsumer(scope=_make_scope_for_match())
    assert await c._get_bans(fake_match) == expected
