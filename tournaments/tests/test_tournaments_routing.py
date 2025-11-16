import pytest
from django.urls.resolvers import RegexPattern
from tournaments import routing
from tournaments import consumers


def _pattern_info(p):
    assert isinstance(p.pattern, RegexPattern)
    return set(p.pattern.regex.groupindex.keys())


def test_websocket_urlpatterns_basic_shape():
    patterns = routing.websocket_urlpatterns
    assert isinstance(patterns, list)
    assert len(patterns) == 3

    p0 = patterns[0]
    assert callable(p0.callback)
    assert "tournament_id" in _pattern_info(p0)
    cls0 = getattr(p0.callback, "cls", None)
    if cls0 is not None:
        assert cls0 is consumers.BracketConsumer

    p1 = patterns[1]
    assert callable(p1.callback)
    assert "tournament_id" in _pattern_info(p1)
    cls1 = getattr(p1.callback, "cls", None)
    if cls1 is not None:
        assert cls1 is consumers.MatchesConsumer

    p2 = patterns[2]
    assert callable(p2.callback)
    groups2 = _pattern_info(p2)
    assert {"tournament_id", "match_id"} <= groups2
    cls2 = getattr(p2.callback, "cls", None)
    if cls2 is not None:
        assert cls2 is consumers.MatchConsumer
