#!/bin/bash

echo "Starting heavy worker..."

cd /app

# The heavy venv is a named volume so a container rebuild does not re-download
# torch. If it is missing, sync once before starting the worker.
if [ ! -x /app/.venv/bin/python ]; then
    echo "Installing heavy dependencies..."
    uv sync --extra heavy
fi

echo "Running migrations..."
uv run python manage.py migrate --noinput

exec uv run python manage.py qcluster
