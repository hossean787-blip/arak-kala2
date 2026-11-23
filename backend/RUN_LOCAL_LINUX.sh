#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export ARAK_DEVELOPMENT=1
python manage.py migrate
printf 'If this is your first run, execute separately: python manage.py setup_manager\n'
python manage.py runserver 127.0.0.1:8000
