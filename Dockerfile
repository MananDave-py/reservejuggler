FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0 \
    DJANGO_STATIC_ROOT=/app/staticfiles

WORKDIR /app

COPY requirements.txt requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . ./
RUN mkdir -p /app/staticfiles
COPY docker-entrypoint.sh /usr/local/bin/moneymaxxer-entrypoint
RUN chmod +x /usr/local/bin/moneymaxxer-entrypoint

EXPOSE 8000
ENTRYPOINT ["moneymaxxer-entrypoint"]
CMD ["sh", "-c", "exec gunicorn rjug.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
