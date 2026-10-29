# Port of the Makefile — same recipe names, Make's multi-name targets as aliases.

compose := "docker compose -f dev/docker-compose.dev.yml"

[parallel]
install: deps-django deps-frontend
    @echo "Installation complete. You can now run the project."

alias i := install

deps-django:
    uv sync

deps-frontend:
    cd frontend && pnpm install

clean:
    rm -rf .venv frontend/node_modules

lint:
    uv run ruff check .

lint-fix:
    uv run ruff check . --fix

format:
    uv run ruff format .

# uvx: pre-commit runs without becoming a project dependency.
precommit:
    uvx pre-commit run --all-files

test:
    DJANGO_SETTINGS_MODULE=config.settings.test uv run pytest

# Part of `test` too, but the build assertions need frontend/dist: run after
# `just vite-build`. Guards Tailwind's @source .svelte line (hard rule 1).
test-assets:
    DJANGO_SETTINGS_MODULE=config.settings.test uv run pytest apps/core/tests/test_frontend.py

# Browser tests against the built assets, not a dev server: ENVIRONMENT=test
# turns off django-vite dev_mode (default "development" points at :5173), which
# then reads the manifest from STATIC_ROOT — hence collectstatic.
# Playwright's sync API runs an event loop, hence DJANGO_ALLOW_ASYNC_UNSAFE.
e2e: vite-build collectstatic
    ENVIRONMENT=test DJANGO_ALLOW_ASYNC_UNSAFE=true DJANGO_SETTINGS_MODULE=config.settings.test uv run --group e2e pytest -m e2e

#### DOCKER DEV ####

dev-up: && (dev-urls "analytics")
    {{compose}} up --build -d

alias dev := dev-up

# Same stack minus analytics (no clickstack): db, app
dev-slim: && dev-urls
    OTEL_ENABLED=false {{compose}} up -d --build db app

# Where the dev stack listens (published on all host interfaces).
dev-urls analytics="":
    @echo ""
    @echo "App         http://localhost:8000          first start installs deps + migrates: just logs"
    @echo "Admin       http://localhost:8000/admin/   create a login: just dev-createsuperuser"
    @echo "Vite HMR    http://localhost:5173          assets only, open the app on :8000"
    @echo "Postgres    internal to the compose network: just dev-psql"
    @if [ -n "{{analytics}}" ]; then echo "ClickStack  http://localhost:8080          OTLP gRPC :4317, HTTP :4318"; else echo "ClickStack  off (dev-slim)"; fi

dev-down:
    {{compose}} down

alias dev-stop := dev-down
alias stop := dev-down

dev-clean:
    {{compose}} down -v

dev-restart: dev-down dev-up

alias restart := dev-restart

dev-logs:
    {{compose}} logs -f

alias logs := dev-logs

dev-ps:
    {{compose}} ps

alias ps := dev-ps

dev-psql:
    {{compose}} exec db psql -U postgres -d db

dev-bash:
    {{compose}} exec app bash

alias bash := dev-bash

dev-shell:
    {{compose}} exec app uv run python manage.py shell -v 2

alias shell := dev-shell

dev-createsuperuser:
    {{compose}} exec app env DJANGO_SUPERUSER_PASSWORD=admin uv run python manage.py createsuperuser --noinput --username admin --email admin@example.com

#### DJANGO MANAGEMENT ####

# These three run inside the dev container (dev/supervisord.conf), where the
# database is reachable as "db". On the host they have no database to talk to.
django-dev:
    DJANGO_SETTINGS_MODULE=config.settings.dev uv run python manage.py runserver 0.0.0.0:8000

vite-dev:
    cd frontend && pnpm run dev --host 0.0.0.0 --port 5173

# django-q2 workers + scheduler
qcluster-dev:
    DJANGO_SETTINGS_MODULE=config.settings.dev uv run python manage.py qcluster

makemigrations:
    uv run python manage.py makemigrations

alias make := makemigrations
alias migrations := makemigrations

# In the running app container: the database has no host port.
migrate:
    {{compose}} exec app uv run python manage.py migrate

#### BUILD ####

vite-build:
    cd frontend && pnpm run build

docker-build:
    docker build -t django-starter-kit .

# Boot the built image (db + web + qcluster) and probe it
smoke-prod image="django-starter-kit":
    prod/smoke.sh {{image}}

# Secrets and hosts below are throwaways so the settings module imports; the
# TLS warnings stay silenced in config/settings/production.py (opt-in policy).
# Django deployment checks against production settings.
check-deploy:
    env DJANGO_SETTINGS_MODULE=config.settings.production ENVIRONMENT=production \
        SECRET_KEY=deploy-check-only-key-0123456789abcdefghijklmnopqrstuvwxyz \
        DEFAULT_FROM_EMAIL=noreply@example.com \
        ALLOWED_HOSTS=example.com \
        CSRF_TRUSTED_ORIGINS=https://example.com \
        uv run python manage.py check --deploy --fail-level WARNING

#### PROD ####

collectstatic:
    uv run python manage.py collectstatic --no-input --clear

prod-start:
    env DJANGO_SETTINGS_MODULE=config.settings.production ENVIRONMENT=production uv run granian \
        --interface asginl \
        --workers 3 \
        --runtime-mode mt \
        --loop uvloop \
        --host 0.0.0.0 \
        --port 8000 \
        config.asgi:application

#### STACK ####

stack-build:
    docker build -t django-starter-kit .

stack-deploy:
    docker stack deploy -c docker-stack.yml django-starter-kit

stack-rm:
    docker stack rm django-starter-kit

stack-logs:
    docker service logs -f django-starter-kit_web

stack-ps:
    docker stack services django-starter-kit
