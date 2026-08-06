#!/usr/bin/env bash
# Render build step. The compiled frontend in frontend/dist is committed to the
# repository, so this stage needs Python only — no Node toolchain required.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
