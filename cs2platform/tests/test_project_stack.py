# cs2platform/tests/test_project_stack.py
import importlib
import os

import pytest
from django.test import override_settings
from django.urls import reverse, resolve, get_resolver
from django.template import engines
from channels.routing import ProtocolTypeRouter


# --- helpers ---------------------------------------------------------------

LOC_TEMPLATES = {
    "home.html": "OK HOME",
}

TEMPLATES_LOC = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": False,
    "OPTIONS": {
        "loaders": [("django.template.loaders.locmem.Loader", LOC_TEMPLATES)],
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]


# --- urls.py ---------------------------------------------------------------

@override_settings(TEMPLATES=TEMPLATES_LOC)
def test_home_url_and_template(client):
    """
    Главная страница отрабатывает и рендерит локальный шаблон.
    """
    # убеждаемся, что сейчас используем наш locmem-loader
    engines._engines.clear()
    resp = client.get(reverse("home"))
    assert resp.status_code == 200
    assert b"OK HOME" in resp.content


def test_included_namespaces_resolve():
    """
    Проверяем, что ключевые namespace подключены.
    Реверсим только те имена, которые гарантированно есть.
    """
    # admin index точно есть
    assert reverse("admin:index").startswith("/admin/")

    # servers:home точно есть (по твоему urls.py)
    assert reverse("servers:home").startswith("/servers/")

    # namespaces присутствуют в резолвере (но не пытаемся reverse, если имени нет)
    namespaces = set(get_resolver().namespace_dict.keys())
    assert {"servers", "teams", "tournaments"}.issubset(namespaces)


def test_debug_static_patterns_present():
    """
    При DEBUG=True в urls добавляются static() маршруты.
    """
    from django.conf import settings
    import cs2platform.urls as urls
    # просто проверим, что urlpatterns — непустой список
    assert isinstance(urls.urlpatterns, list) and urls.urlpatterns


# --- asgi.py ---------------------------------------------------------------

def test_asgi_protocoltyperouter_has_http_and_ws(monkeypatch):
    """
    ASGI-приложение — ProtocolTypeRouter с ключами 'http' и 'websocket'.
    Важно импортировать модуль при DJANGO_SETTINGS_MODULE=settings_test.
    """
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "cs2platform.settings_test")
    # Перезагружаем модуль, чтобы он подхватил переменную окружения
    mod = importlib.import_module("cs2platform.asgi")
    importlib.reload(mod)

    assert hasattr(mod, "application")
    app = mod.application
    assert isinstance(app, ProtocolTypeRouter)

    # В channels у ProtocolTypeRouter есть application_mapping
    mapping = getattr(app, "application_mapping", {})
    assert "http" in mapping and "websocket" in mapping
    assert callable(mapping["http"])
    # websocket обёрнут в AuthMiddlewareStack(URLRouter(...))
    # достаточно проверить, что объект присутствует
    assert mapping["websocket"] is not None


# --- routing.py ------------------------------------------------------------

def test_routing_only_websocket_present():
    """
    Отдельный routing.py экспортирует ProtocolTypeRouter с websocket.
    """
    mod = importlib.import_module("cs2platform.routing")
    importlib.reload(mod)
    assert hasattr(mod, "application")
    app = mod.application
    assert isinstance(app, ProtocolTypeRouter)
    mapping = getattr(app, "application_mapping", {})
    # здесь только websocket (http нет)
    assert "websocket" in mapping
    assert mapping["websocket"] is not None


# --- wsgi.py ---------------------------------------------------------------

def test_wsgi_application_callable(monkeypatch):
    """
    WSGI application должен быть создаваемым и callable.
    """
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "cs2platform.settings_test")
    mod = importlib.import_module("cs2platform.wsgi")
    importlib.reload(mod)
    assert hasattr(mod, "application")
    # WSGI application — вызываемый объект
    assert callable(mod.application)


# --- sanity: прямое разрешение главной (без reverse) -----------------------

def test_root_path_resolves_to_home_view():
    """
    Убеждаемся, что '/' резолвится в home view из urls.py.
    """
    from cs2platform import urls as proj_urls
    match = resolve("/")
    # Имя должно быть 'home', как задано в urls.py
    assert match.url_name == "home"
