#!/usr/bin/env bash
gunicorn app:app --bind 0.0.0.0:8001 --timeout 0