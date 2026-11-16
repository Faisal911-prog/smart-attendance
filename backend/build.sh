#!/usr/bin/env bash
# Build script used by Render (see ../render.yaml). Exits on the first error.
set -o errexit

pip install -r requirements.txt

# The migration files must be committed to Git (run "makemigrations" once locally).
if [ ! -f accounts/migrations/0001_initial.py ] || [ ! -f attendance/migrations/0001_initial.py ]; then
  echo "ERROR: migration files are missing."
  echo "Run: python manage.py makemigrations accounts attendance   (then commit the migrations/ folders)"
  exit 1
fi

python manage.py collectstatic --no-input
python manage.py migrate --no-input
