#!/usr/bin/env bash
set -e

# Ждём Postgres (простая проверка)
if [ -n "$POSTGRES_HOST" ]; then
  echo "Waiting for PostgreSQL at $POSTGRES_HOST:$POSTGRES_PORT..."
  until nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 0.5
  done
fi

# Миграции и статика
python manage.py migrate --noinput
python manage.py collectstatic --noinput || true

# Запускаем Daphne (ASGI для Channels)
# daphne будет слушать на 0.0.0.0:8000 и забирать приложение из ASGI_APPLICATION
exec daphne -b 0.0.0.0 -p 8000 cs2platform.asgi:application
