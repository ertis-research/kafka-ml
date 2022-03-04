#!/usr/bin/env bash
#python app.py
gunicorn app:app --bind 0.0.0.0:8002 --timeout 0