# CS2 Platform

A Django-based platform for hosting CS2 tournaments: teams, brackets, veto workflow, match pages, and live updates via WebSockets (Channels).

## Tech Stack
- **Django 5**, **Django REST Framework**
- **Django Channels** + **Redis** (WebSockets)
- **PostgreSQL**
- **Docker / docker compose**
- **pytest** for tests
- **Whitenoise** for static files

---

## Quick Start (Docker)

1) Create a `.env` from the example:
```bash
cp .env.example .env
# Edit .env and fill in secrets/keys

2)Build and start:

docker compose build
docker compose up -d

3)Run migrations and create a superuser:

docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser


4)Open:

App: http://localhost:8000

Admin: http://localhost:8000/admin

If you use django.contrib.sites, create a Site record with domain localhost:8000.

Stop:

docker compose down


5)Environment Variables

# Django
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000

# API keys
FACEIT_API_KEY=...
STEAM_WEB_API_KEY=...

# Database
POSTGRES_DB=cs2db
POSTGRES_USER=cs2user
POSTGRES_PASSWORD=changeme
POSTGRES_HOST=db        # Docker: db, Local: localhost
POSTGRES_PORT=5432

# Channels / Redis
REDIS_URL=redis://redis:6379/0


6)Local Development (without Docker)

Requires PostgreSQL and Redis installed locally.

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # edit it

python manage.py migrate
python manage.py runserver

7)Running Tests
pytest -q
# or inside Docker:
docker compose exec web pytest -q

8)Common Commands

Collect static (if needed):

docker compose exec web python manage.py collectstatic --noinput


Fresh DB (dev):

docker compose down -v
docker compose up -d
docker compose exec web python manage.py migrate


Logs:

docker compose logs -f web

9)Project Structure (short)
cs2platform/
  accounts/ teams/ servers/ tournaments/   # Django apps
  cs2platform/                             # settings, urls, asgi, wsgi
  static/ staticfiles/ media/
docker-compose.yml
Dockerfile
docker/entrypoint.sh
requirements.txt
