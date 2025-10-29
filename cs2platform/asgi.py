# cs2platform/asgi.py
import os
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cs2platform.settings")

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()  # ← это запускает django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import tournaments.routing  # ← импортируем после get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(tournaments.routing.websocket_urlpatterns)
    ),
})
