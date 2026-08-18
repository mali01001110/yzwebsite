#!/usr/bin/env bash
# Render build step. The compiled frontend in frontend/dist is committed to the
# repository, so this stage needs Python only — no Node toolchain required.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Migrations deliberately do NOT run here. Render's build environment cannot
# resolve the database's internal hostname, so `migrate` fails the build before
# anything is deployed. It runs from the service's preDeployCommand instead,
# which executes with network access after the build and before the new
# instance starts. collectstatic needs no database, so it stays.
python manage.py collectstatic --no-input
