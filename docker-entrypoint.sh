#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py seed_dummy_users
exec python manage.py runserver 0.0.0.0:8000 --noreload
