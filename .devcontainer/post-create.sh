#!/usr/bin/env bash
# Compose has already waited for database health and successful migrations.
set -euo pipefail
python manage.py seed_development_data
python scripts/check_dev_environment.py
