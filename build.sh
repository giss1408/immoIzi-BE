#!/usr/bin/env bash
# Render build step: install, collect static files, migrate, optionally seed.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

cd immoizi
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Test environments only: create the landlord_demo / tenant_demo /
# seeker_demo accounts and sample listings. Safe to re-run (get_or_create).
if [ "${SEED_DEMO_DATA:-False}" = "True" ]; then
  if [ -z "${DEMO_PASSWORD:-}" ]; then
    echo "SEED_DEMO_DATA=True requires DEMO_PASSWORD" >&2
    exit 1
  fi
  python manage.py seed_demo_data --password "$DEMO_PASSWORD"
fi

# Optional admin account (Render's free plan has no shell). Uses Django's
# DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ]; then
  python manage.py shell -c "
from django.contrib.auth import get_user_model
import sys
sys.exit(0 if get_user_model().objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists() else 1)
" || python manage.py createsuperuser --no-input
fi
