import os
from dotenv import load_dotenv
load_dotenv(".env.local")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cs2platform.settings.local")

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import tournaments.routing 

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(tournaments.routing.websocket_urlpatterns)
    ),
})
