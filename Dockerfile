FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=1 \
    DJANGO_DB_PATH=/data/db.sqlite3 \
    DJANGO_STATIC_ROOT=/data/staticfiles

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
RUN mkdir -p /data
COPY docker-entrypoint.sh /usr/local/bin/moneymaxxer-entrypoint
RUN chmod +x /usr/local/bin/moneymaxxer-entrypoint

EXPOSE 8000
VOLUME ["/data"]
ENTRYPOINT ["moneymaxxer-entrypoint"]
