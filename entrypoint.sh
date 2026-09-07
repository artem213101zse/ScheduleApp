#!/bin/sh
set -e

mkdir -p /app/data
export DATABASE_PATH="${DATABASE_PATH:-/app/data/db.sqlite3}"

# Если volume пустой — берём базу из образа (собранную на вашей машине)
if [ ! -f "$DATABASE_PATH" ] && [ -f /app/db.sqlite3 ]; then
    cp /app/db.sqlite3 "$DATABASE_PATH"
fi

python manage.py migrate --noinput

python - <<'PY'
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ScheduleApp.settings")
django.setup()
from django.contrib.auth.models import User
from django.core.management import call_command

if not User.objects.exists():
    call_command("loaddata", "initial")
PY

exec gunicorn ScheduleApp.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 2 \
    --access-logfile -
