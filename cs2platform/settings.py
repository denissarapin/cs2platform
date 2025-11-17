from pathlib import Path
import os

# ================== BASE ==================
BASE_DIR = Path(__file__).resolve().parent.parent

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
DEBUG = env_bool("DJANGO_DEBUG", True)

# Никогда не держим продовый ключ в коде:
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-insecure-key-only-for-local"  # для локалки/тестов
)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["*"] if DEBUG else [])

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

AUTH_USER_MODEL = "accounts.User"

# ================== Third-party keys ==================
FACEIT_API_KEY = os.getenv("FACEIT_API_KEY", "")
STEAM_WEB_API_KEY = os.getenv("STEAM_WEB_API_KEY", "")
# Если очень хочешь жёстко требовать ключи на проде:
if not DEBUG and not FACEIT_API_KEY:
    raise RuntimeError("FACEIT_API_KEY is not set")

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
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # до SessionMiddleware — ок
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
    REDIS_PORT = os.getenv("REDIS_PORT", "6379")
    if REDIS_HOST:
        CHANNEL_LAYERS = {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {"hosts": [(REDIS_HOST, int(REDIS_PORT))]},
            }
        }
    else:
        # Локально/в тестах — без Redis
        CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# ================== Database ==================
# 1) Если есть DATABASE_URL — используем его (например, от докера)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # без dj-database-url: парсим вручную простые варианты postgres://user:pass@host:port/db
    import urllib.parse as _url
    p = _url.urlparse(DATABASE_URL)
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
    # 2) Иначе берем значения из переменных среды (как у тебя было)…
    DB = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "cs2db"),
        "USER": os.getenv("POSTGRES_USER", "cs2user"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "mint123"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),   # <-- было "localhost"
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
    # 3) …а если DEBUG и Postgres не доступен — можно упростить жизнь SQLite:
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

# ================== Static / Media ==================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
