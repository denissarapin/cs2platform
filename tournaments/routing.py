from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/tournaments/(?P<tournament_id>\d+)/bracket/?$", consumers.BracketConsumer.as_asgi()),
    re_path(r"ws/tournaments/(?P<tournament_id>\d+)/matches/$", consumers.MatchesConsumer.as_asgi()),
    re_path(r"ws/tournaments/(?P<tournament_id>\d+)/matches/(?P<match_id>\d+)/$", consumers.MatchConsumer.as_asgi()),
]
