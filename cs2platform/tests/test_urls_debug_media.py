# cs2platform/tests/test_urls_debug_media.py
import importlib
import re

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import clear_url_caches


def _reload_urls():
    """
    Сбрасываем кэш резолвера и перезагружаем модуль urls,
    чтобы отработал модульный код с if settings.DEBUG.
    """
    import cs2platform.urls as urls_mod
    clear_url_caches()
    return importlib.reload(urls_mod)


def _has_media_static_pattern(urlpatterns) -> bool:
    """
    Ищем среди urlpatterns те, что добавляет django.conf.urls.static.static().
    В Django 5 это re_path, т.е. у pattern есть .regex.
    """
    media = settings.MEDIA_URL.lstrip("/").rstrip("/")
    for p in urlpatterns:
        pat = getattr(p, "pattern", None)
        regex = getattr(pat, "regex", None)
        if regex and re.search(rf"{re.escape(media)}/?", regex.pattern):
            return True
    return False


@override_settings(DEBUG=True, MEDIA_URL="/media/", MEDIA_ROOT="/tmp/media")
def test_urls_appends_static_patterns_when_debug_true(tmp_path):
    urls = _reload_urls()
    assert _has_media_static_pattern(urls.urlpatterns), "Ожидали наличие static(MEDIA_URL) при DEBUG=True"


@override_settings(DEBUG=False, MEDIA_URL="/media/", MEDIA_ROOT="/tmp/media")
def test_urls_does_not_append_static_patterns_when_debug_false():
    urls = _reload_urls()
    assert not _has_media_static_pattern(urls.urlpatterns), "Не ожидали static(MEDIA_URL) при DEBUG=False"
