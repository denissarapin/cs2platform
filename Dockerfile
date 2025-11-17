# Python base
FROM python:3.12-slim

# Системные пакеты (gcc, libpq – для psycopg2-binary не обязательно, но полезно)
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-traditional curl && \
    rm -rf /var/lib/apt/lists/*

# Внутри контейнера будем работать в /app
WORKDIR /app

# Скопируем только requirements — чтобы кэшировались слои
COPY requirements.txt /app/

# Установка зависимостей
RUN pip install --no-cache-dir -r /app/requirements.txt

# Копируем весь проект
COPY . /app

# Соберём статику в образе (на проде полезно; локально тоже не мешает)
# collectstatic не упадёт, если нет настроенных STATICFILES — ok
RUN python manage.py collectstatic --noinput || true

# Скрипт-входная точка: подождать БД, миграции и старт daphne
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Порт
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
