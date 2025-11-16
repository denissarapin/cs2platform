
import pytest
from django.template import engines
import copy

TEMPLATES_MAP = {
    "servers/server_list.html": """
    {% for m in modes %}
      {{ m.code }} {{ m.title }} {{ m.players_total }}
    {% endfor %}
    """,
    "servers/mode.html": """
    {{ mode.code }} {{ active_mode }}
    {% for s in servers %}{{ s.ip }} {{ s.map }}{% endfor %}
    """,
}

@pytest.fixture(autouse=True)
def _override_templates(settings):
    prev = copy.deepcopy(settings.TEMPLATES)

    new_tpl = copy.deepcopy(settings.TEMPLATES)
    new_tpl[0]["APP_DIRS"] = False
    new_tpl[0].setdefault("OPTIONS", {})["loaders"] = [
        ("django.template.loaders.locmem.Loader", TEMPLATES_MAP),
        "django.template.loaders.filesystem.Loader",
        "django.template.loaders.app_directories.Loader",
    ]
    settings.TEMPLATES = new_tpl
    engines._engines.clear()   
    yield
    settings.TEMPLATES = prev
    engines._engines.clear()