#!/bin/bash

echo "Starting application initialization..."

# Change to the app directory
cd /app

# .venv and frontend/node_modules are named volumes. A container that lost them
# silently runs from leftovers in the bind mount instead: a stale .venv then
# serves pages whose errors cannot even be rendered, which is impossible to
# diagnose from the browser. Stop before that.
for path in /app/.venv /app/frontend/node_modules; do
    if ! grep -q " $path " /proc/mounts; then
        echo "ERROR: $path is not a mounted volume."
        echo "Recreate the stack: docker compose -f dev/docker-compose.dev.yml down && just dev"
        exit 1
    fi
done

# Install dependencies (let uv and pnpm handle caching)
echo "Installing dependencies..."
just install

# compose waits for the db healthcheck, so the database is reachable here.
echo "Running migrations..."
uv run python manage.py migrate --noinput

# Add node_modules/.bin to PATH for vite command
export PATH="/app/frontend/node_modules/.bin:$PATH"

echo "Starting supervisord..."
# Start supervisord
exec uv run supervisord -c /etc/supervisor/supervisord.conf
