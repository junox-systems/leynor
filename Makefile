MAKEFLAGS += -j4

.PHONY: install i
install i: deps-django deps-frontend
	@echo "Installation complete. You can now run the project."

.PHONY: deps-django
deps-django:
	uv sync

.PHONY: deps-frontend
deps-frontend:
	cd frontend && pnpm install

.PHONY: clean
clean:
	rm -rf .venv frontend/node_modules

.PHONY: lint
lint:
	uv run ruff check .

.PHONY: lint-fix
lint-fix:
	uv run ruff check . --fix

.PHONY: format
format:
	uv run ruff format .

.PHONY: test
test:
	DJANGO_SETTINGS_MODULE=config.settings.test uv run pytest

#### DOCKER DEV #### -----------------------------------------------------------------------------
.PHONY: dev-up dev
dev-up dev:
	docker compose -f dev/docker-compose.dev.yml up --build -d
	@$(MAKE) --no-print-directory dev-urls ANALYTICS=1

# Same stack minus analytics (no clickstack): db, app
.PHONY: dev-slim
dev-slim:
	OTEL_ENABLED=false docker compose -f dev/docker-compose.dev.yml up -d --build db app
	@$(MAKE) --no-print-directory dev-urls

# Where the dev stack listens (published on all host interfaces).
.PHONY: dev-urls
dev-urls:
	@echo ""
	@echo "App         http://localhost:8000          first start installs deps + migrates: make dev-logs"
	@echo "Admin       http://localhost:8000/admin/   create a login: make dev-createsuperuser"
	@echo "Vite HMR    http://localhost:5173          assets only, open the app on :8000"
	@echo "Postgres    internal to the compose network: make dev-psql"
	@if [ -n "$(ANALYTICS)" ]; then echo "ClickStack  http://localhost:8080          OTLP gRPC :4317, HTTP :4318"; else echo "ClickStack  off (dev-slim)"; fi

.PHONY: dev-down dev-stop
dev-down dev-stop stop:
	docker compose -f dev/docker-compose.dev.yml down

.PHONY: dev-clean
dev-clean:
	docker compose -f dev/docker-compose.dev.yml down -v

.PHONY: dev-restart restart
dev-restart restart:
	make dev-down
	make dev-up

.PHONY: dev-logs
dev-logs logs:
	docker compose -f dev/docker-compose.dev.yml logs -f

.PHONY: dev-ps
dev-ps ps:
	docker compose -f dev/docker-compose.dev.yml ps

.PHONY: dev-psql
dev-psql:
	docker compose -f dev/docker-compose.dev.yml exec db psql -U postgres -d db

.PHONY: dev-bash bash
dev-bash bash:
	docker compose -f dev/docker-compose.dev.yml exec app bash

.PHONY: dev-shell shell
dev-shell shell:
	docker compose -f dev/docker-compose.dev.yml exec app uv run python manage.py shell -v 2

dev-createsuperuser:
	docker compose -f dev/docker-compose.dev.yml exec app env DJANGO_SUPERUSER_PASSWORD=admin uv run python manage.py createsuperuser --noinput --username admin --email admin@example.com

## - END DOCKER DEV - ## -------------------------------------------------------------------------

#### - DJANGO MANAGEMENT - #### ---------------------------------------------------------------------
# These three run inside the dev container (dev/supervisord.conf), where the
# database is reachable as "db". On the host they have no database to talk to.
.PHONY: django-dev
django-dev:
	DJANGO_SETTINGS_MODULE=config.settings.dev uv run python manage.py runserver 0.0.0.0:8000

.PHONY: vite-dev
vite-dev:
	cd frontend && pnpm run dev --host 0.0.0.0 --port 5173

# django-q2 workers + scheduler
.PHONY: qcluster-dev
qcluster-dev:
	DJANGO_SETTINGS_MODULE=config.settings.dev uv run python manage.py qcluster

.PHONY: makemigrations make migrations
makemigrations make migrations:
	uv run python manage.py makemigrations

# In the running app container: the database has no host port.
.PHONY: migrate
migrate:
	docker compose -f dev/docker-compose.dev.yml exec app uv run python manage.py migrate
## - END DEV - ## ---------------------------------------------------------------------------

#### - BUILD - #### ------------------------------------------------------------------------------
.PHONY: vite-build
vite-build:
	cd frontend && pnpm run build

.PHONY: docker-build
docker-build:
	docker build -t django-starter-kit .

.PHONY: smoke-prod
smoke-prod:
	prod/smoke.sh django-starter-kit
## - END BUILD - ## -------------------------------------------------------------------------------

### - PROD - ### ---------------------------------------------------------------------------------
.PHONY: collectstatic
collectstatic:
	uv run python manage.py collectstatic --no-input --clear

.PHONY: prod-start
prod-start:
	env DJANGO_SETTINGS_MODULE=config.settings.production ENVIRONMENT=production uv run granian \
		--interface asginl \
		--workers 3 \
		--runtime-mode mt \
	--loop uvloop \
		--host 0.0.0.0 \
		--port 8000 \
		config.asgi:application

## - END PROD - ## -------------------------------------------------------------------------------

#### - STACK - #### ------------------------------------------------------------------------------
.PHONY: stack-build
stack-build:
	docker build -t django-starter-kit .

.PHONY: stack-deploy
stack-deploy:
	docker stack deploy -c docker-stack.yml django-starter-kit

.PHONY: stack-rm
stack-rm:
	docker stack rm django-starter-kit

.PHONY: stack-logs
stack-logs:
	docker service logs -f django-starter-kit_web

.PHONY: stack-ps
stack-ps:
	docker stack services django-starter-kit
## - END STACK - ##

# deploy:
# 	# This target is for deployment, which is not part of the automated CI/CD pipeline.
# 	# Add your deployment commands here if you need to deploy manually.
# 	echo "Deployment is not automated in CI/CD. Please deploy manually if needed."
