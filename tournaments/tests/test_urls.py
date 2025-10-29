import pytest
from django.urls import reverse, resolve

# список (имя, kwargs) — только проверяем, что reverse работает
ROUTES = [
    ("tournaments:list",            {}),
    ("tournaments:create",          {}),
    ("tournaments:overview",        {"pk": 1}),
    ("tournaments:bracket",         {"pk": 1}),
    ("tournaments:matches",         {"pk": 1}),
    ("tournaments:teams",           {"pk": 1}),
    ("tournaments:results",         {"pk": 1}),
    ("tournaments:generate_bracket",{"pk": 1}),
    ("tournaments:toggle_registration", {"pk": 1}),
    ("tournaments:start",           {"pk": 1}),
    ("tournaments:report_match",    {"pk": 1, "match_id": 2}),
    ("tournaments:register_team",   {"pk": 1, "team_id": 3}),
    ("tournaments:match_detail",    {"pk": 1, "match_id": 2}),
    ("tournaments:match_veto",      {"pk": 1, "match_id": 2}),
    ("tournaments:api_tournament_list", {}),
    ("tournaments:api_tournament_detail", {"pk": 1}),
    ("tournaments:api_report_match", {"pk": 1}),
    ("tournaments:settings",        {"pk": 1}),
]

@pytest.mark.parametrize("name,kwargs", ROUTES)
def test_named_routes_reverse_ok(name, kwargs):
    url = reverse(name, kwargs=kwargs)  # не должно падать
    match = resolve(url)
    # Достаточно проверить, что наш namespace/имя совпадает
    assert match.namespace == "tournaments"
    assert match.url_name == name.split(":")[1]
