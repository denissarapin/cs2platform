from pathlib import Path
import os
import urllib.parse as urlparse

# ================== BASE DIR ==================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ================== helpers ===================
def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in {"1", "true", "yes", "on"}

def env_list(name: str, default=None):
    raw = os.getenv(name)
    if not raw:
        return default or []
    return [x.strip() for x in raw.split(",") if x.strip()]

# ------------------ Core switches ------------------
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-insecure-key-only-for-local"
)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["*"] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

AUTH_USER_MODEL = "accounts.User"

# ================== Third-party keys ==================
FACEIT_API_KEY = os.getenv("FACEIT_API_KEY", "")
STEAM_WEB_API_KEY = os.getenv("STEAM_WEB_API_KEY", "")

TOURNAMENT_MIN_TEAMS = int(os.getenv("TOURNAMENT_MIN_TEAMS", "4"))
SITE_ID = int(os.getenv("DJANGO_SITE_ID", "1"))

# ================== Apps ==================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django.contrib.sites",
    "django.contrib.humanize",
    "channels",
    "accounts",
    "teams",
    "servers",
    "tournaments",
    "storages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    )
}

ROOT_URLCONF = "cs2platform.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = "cs2platform.asgi.application"
WSGI_APPLICATION = "cs2platform.wsgi.application"

# ================== Channels / Redis ==================
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    if REDIS_HOST:
        CHANNEL_LAYERS = {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {"hosts": [(REDIS_HOST, REDIS_PORT)]},
            }
        }
    else:
        CHANNEL_LAYERS = {
            "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
        }

# ================== Database ==================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    p = urlparse.urlparse(DATABASE_URL)
    if p.scheme.startswith("postgres"):
        DB = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": p.path.lstrip("/"),
            "USER": p.username or "",
            "PASSWORD": p.password or "",
            "HOST": p.hostname or "",
            "PORT": str(p.port or ""),
        }
    else:
        raise RuntimeError(f"Unsupported DATABASE_URL scheme: {p.scheme}")
else:
    DB = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "cs2db"),
        "USER": os.getenv("POSTGRES_USER", "cs2user"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "mint123"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
    if DEBUG and os.getenv("USE_SQLITE", "0") == "1":
        DB = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }

DATABASES = {"default": DB}

# ================== i18n/time ==================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ================== Static / Media (defaults) =========
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
