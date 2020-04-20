#!/usr/bin/env bash
python manage.py makemigrations --noinput
python manage.py migrate
gunicorn autoweb.wsgi:application --bind 0.0.0.0:8000