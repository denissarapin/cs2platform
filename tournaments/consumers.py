import json
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from tournaments.models import Match, MAP_POOL
from tournaments.services import perform_ban, get_final_map, get_available_maps

class BracketConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tournament_id = self.scope["url_route"]["kwargs"]["tournament_id"]
        self.group_name = f"tournament_{self.tournament_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def bracket_update(self, event):
        match_id = event["match_id"]

        match = await self.get_match(match_id)

        html = await sync_to_async(render_to_string)(
            "tournaments/_match.html",
            {"match": match},
        )

        await self.send(
            text_data=json.dumps(
                {
                    "type": "bracket_update",
                    "match_id": match_id,
                    "html": html,
                }
            )
        )

    @sync_to_async
    def get_match(self, match_id):
        return Match.objects.select_related("team_a", "team_b", "winner").get(pk=match_id)

class MatchesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tournament_id = self.scope["url_route"]["kwargs"]["tournament_id"]
        self.group_name = f"tournament_matches_{self.tournament_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"[WS] MatchesConsumer connected for tournament {self.tournament_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def matches_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "matches_update",
                    "action": event["action"],
                    "message": event.get("message", ""),
                }
            )
        )

class MatchConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tournament_id = int(self.scope["url_route"]["kwargs"]["tournament_id"])
        self.match_id = int(self.scope["url_route"]["kwargs"]["match_id"])
        self.group_name = f"match_{self.match_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            return

        msg_type = data.get("type")
        if msg_type == "heartbeat":
            match = await self._get_match()
            changed = await sync_to_async(match.auto_ban_if_expired)()  # bool
            if changed:
                await self._broadcast_update()
            return

        if msg_type != "ban_map":
            return

        map_name = data.get("map_name")
        if not map_name:
            return

        match = await self._get_match()
        await sync_to_async(match.auto_ban_if_expired)()
        ban_count = await self._ban_count(match)
        current_team = match.team_a if (ban_count % 2 == 0) else match.team_b
        user = self.scope.get("user")
        is_allowed = (
            getattr(user, "is_authenticated", False)
            and (
                getattr(user, "is_staff", False) or
                (current_team is not None and getattr(current_team, "captain_id", None) == user.id)
            )
        )

        if not is_allowed or current_team is None:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Insufficient permissions or no team assigned for banning"
            }))
            return

        ok = await sync_to_async(match.ban_map)(map_name, current_team, action="ban")
        if not ok:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "This map is no longer available for banning or it is not your turn"
            }))
            return
        await self._broadcast_update()

    async def _broadcast_update(self):
        match = await self._get_match()
        available_codes = await sync_to_async(get_available_maps)(match)
        code = match.final_map_code
        if not code and len(available_codes) == 1:
            code = available_codes[0]

        final_map = None
        if code:
            label = dict(MAP_POOL).get(code, code)
            final_map = (code, label)

        bans = await self._get_bans(match)
        ban_count = await self._ban_count(match)
        current_team = match.team_a if (ban_count % 2 == 0) else match.team_b

        html = await sync_to_async(render_to_string)(
            "tournaments/match_detail_inner.html",
            {
                "tournament": match.tournament,
                "match": match,
                "bans": bans,
                "map_pool": MAP_POOL,
                "available_codes": available_codes,
                "final_map": final_map,
                "current_team": current_team,
            },
        )

        veto_html = await sync_to_async(render_to_string)(
            "tournaments/_veto_panel.html",
            {
                "tournament": match.tournament,
                "match": match,
                "bans": bans,
                "map_pool": MAP_POOL,
                "available_codes": available_codes,
                "final_map": final_map,
                "current_team": current_team,
            },
        )

        show_veto_btn = bool(final_map)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "match_update",
                "html": html,
                "veto_html": veto_html,
                "show_veto_btn": show_veto_btn,
            },
        )

    async def match_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "match_update",
            "html": event.get("html", ""),
            "veto_html": event.get("veto_html", ""),
            "show_veto_btn": event.get("show_veto_btn"),
        }))

    @sync_to_async
    def _get_match(self):
        return Match.objects.select_related("tournament", "team_a", "team_b").get(pk=self.match_id)

    @sync_to_async
    def _ban_count(self, match):
        return match.map_bans.count()

    @sync_to_async
    def _get_bans(self, match):
        return list(match.map_bans.select_related("team").order_by("order"))
