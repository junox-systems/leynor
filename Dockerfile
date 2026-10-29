# syntax=docker/dockerfile:1

#### Builder stage
FROM debian:trixie-slim AS builder

ARG MISE_VERSION=2026.8.0

ENV UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    MISE_DATA_DIR=/opt/mise

# Debian's x86-64 baseline runs on v2 CPUs; AlmaLinux/RHEL 10 require v3.
# No compiler: every dependency ships prebuilt wheels/binaries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://github.com/jdx/mise/releases/download/v${MISE_VERSION}/mise-v${MISE_VERSION}-linux-$(uname -m | sed 's/x86_64/x64/;s/aarch64/arm64/').tar.xz" \
    | tar -xJf - -C /usr/local/bin --strip-components=2 mise/bin/mise

WORKDIR /app

SHELL ["/bin/bash", "-c"]

COPY mise.toml /app/mise.toml
COPY pyproject.toml uv.lock /app/
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./frontend/

RUN mise trust && mise install

ENV PATH="/opt/mise/shims:${PATH}"

RUN uv sync --frozen && \
    cd frontend && pnpm install --frozen-lockfile

COPY . .

RUN just vite-build && \
    just collectstatic

# Prune dev deps; this venv ships in the runtime stage.
RUN uv sync --frozen --no-dev

#### Runtime stage
# No mise/uv here: interpreter + prod venv come prebuilt from the builder.
FROM debian:trixie-slim AS runtime

ENV ENVIRONMENT=production \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:${PATH}"

# curl is the healthcheck client.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash django_user

WORKDIR /app
RUN chown django_user:django_user /app

# Same path as the builder: the venv's python symlink points here.
COPY --from=builder /opt/mise/installs/python /opt/mise/installs/python
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/staticfiles /app/staticfiles
COPY --from=builder /app/frontend/dist /app/frontend/dist
COPY --chown=django_user:django_user . .

COPY prod/init.sh /init.sh
RUN chmod +x /init.sh && chown django_user:django_user /init.sh

USER django_user

# Host header: /healthz/ goes through ALLOWED_HOSTS, which must include localhost.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS -H "Host: localhost" http://127.0.0.1:8000/healthz/ || exit 1

EXPOSE 8000

ENTRYPOINT ["/init.sh"]
CMD ["granian", "--interface", "asginl", "--workers", "3", "--runtime-mode", "mt", "--loop", "uvloop", "--host", "0.0.0.0", "--port", "8000", "config.asgi:application"]
