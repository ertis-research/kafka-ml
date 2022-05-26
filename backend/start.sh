#!/usr/bin/env bash
python manage.py makemigrations --noinput
python manage.py migrate --run-syncdb
# gunicorn autoweb.wsgi:application --bind 0.0.0.0:8000 --timeout 0
daphne  -b 0.0.0.0 -p 8000 -t 0 autoweb.asgi:application