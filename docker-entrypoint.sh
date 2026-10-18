#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput
if [ "${SEED_DEMO_USERS:-0}" = "1" ]; then
    python manage.py seed_dummy_users
fi
if [ "${SEED_DEMO_SAMPLE:-0}" = "1" ]; then
    python manage.py seed_demo_sample
fi
exec "$@"
