#!/usr/bin/env bash
gunicorn app:app --bind 0.0.0.0:8002 --timeout 0