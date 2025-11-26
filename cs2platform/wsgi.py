import os
from dotenv import load_dotenv

load_dotenv(".env.local")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cs2platform.settings.local")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()