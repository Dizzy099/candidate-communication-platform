#!/bin/sh
# Entry point for the single-container demo deployment.
# Only the Next.js server is public ($PORT). The API, worker and simulator
# listen on 127.0.0.1 inside the container; /api/* is proxied by Next.js.
set -e

random() { python -c "import secrets; print(secrets.token_urlsafe(32))"; }

# Secrets: use the platform's values if set, otherwise generate per boot.
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-$(random)}"
export SIM_DJANGO_SECRET_KEY="${SIM_DJANGO_SECRET_KEY:-$(random)}"
export PROVIDER_API_KEY="${PROVIDER_API_KEY:-$(random)}"
export PROVIDER_WEBHOOK_SECRET="${PROVIDER_WEBHOOK_SECRET:-$(random)}"
export SIM_API_KEY="$PROVIDER_API_KEY"
export SIM_WEBHOOK_SECRET="$PROVIDER_WEBHOOK_SECRET"

export DJANGO_DEBUG=false
export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"
export DJANGO_SECURE_COOKIES="${DJANGO_SECURE_COOKIES:-true}"
export PROVIDER_BASE_URL="http://127.0.0.1:8001"
export PUBLIC_WEBHOOK_BASE_URL="http://127.0.0.1:8000"
export DEMO_CONTROLS_ENABLED="${DEMO_CONTROLS_ENABLED:-true}"
export SIM_ALLOWED_HOSTS="127.0.0.1,localhost"
export DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$DATA_DIR/app.sqlite3}"
export SIM_DATABASE_URL="${SIM_DATABASE_URL:-sqlite:///$DATA_DIR/simulator.sqlite3}"
export APP_PORT="${PORT:-3000}"

(cd backend && python manage.py migrate --noinput && (python manage.py seed_demo || true))
(cd simulator && python manage.py migrate --noinput)

exec honcho -f Procfile start
