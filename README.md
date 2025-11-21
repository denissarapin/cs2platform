# CS2 Platform

A Django-based platform for hosting and managing CS2 tournaments with real-time features.
Includes team management, registration workflow, full tournament brackets, match pages, CS2-style map veto, and live updates powered by Django Channels.

# Key Features

Tournament lifecycle (registration → bracket → matches → results → finish)

Single-elimination bracket generation & progression (service layer + atomic DB updates)

Real-time UI updates via WebSockets (Channels + Redis) using server-rendered HTML fragments

Match pages with live updates: scores, bans, veto flow, final map

CS2-style map veto system with turn-based banning logic and captain-only actions

Role-based access control for staff and tournament admins

REST API endpoints for tournaments and matches (DRF)

HTMX-enhanced views for dynamic forms and partial updates without a full SPA

# Tech Stack

Django 5, Django REST Framework

Django Channels + Redis (WebSockets)

PostgreSQL

Docker / docker compose

pytest for tests

Whitenoise for static files

# Quick Start (Docker)
1) Create .env
cp .env.example .env

2) Build & start
docker compose build
docker compose up -d

3) Migrate & create superuser
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser

4) Open

App: http://localhost:8000

Admin: http://localhost:8000/admin

If you use django.contrib.sites, add a Site with domain localhost:8000.

Stop
docker compose down

# Environment Variables
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000

FACEIT_API_KEY=...
STEAM_WEB_API_KEY=...

POSTGRES_DB=cs2db
POSTGRES_USER=cs2user
POSTGRES_PASSWORD=changeme
POSTGRES_HOST=db
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0

# Local Development (without Docker)

Requires PostgreSQL + Redis installed locally.

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # edit it

python manage.py migrate
python manage.py runserver

# Running Tests
pytest -q
or inside Docker:
docker compose exec web pytest -q

# Common Commands

Collect static:

docker compose exec web python manage.py collectstatic --noinput


Fresh dev DB:

docker compose down -v
docker compose up -d
docker compose exec web python manage.py migrate


Logs:

docker compose logs -f web

# Project Structure (short)
cs2platform/
  accounts/ teams/ servers/ tournaments/    
  cs2platform/ 
  static/ staticfiles/ media/
docker-compose.yml
Dockerfile
docker/entrypoint.sh
requirements.txt
