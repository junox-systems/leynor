# Debian's x86-64 baseline runs on v2 CPUs; AlmaLinux/RHEL 10 require v3.
FROM debian:trixie-slim

ARG MISE_VERSION=2026.8.0

# set environment variables
ENV ENVIRONMENT=development \
    UV_NO_CACHE=1

# git for pre-commit and VCS work inside the container. No compiler: every
# dependency ships prebuilt wheels/binaries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl xz-utils git \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://github.com/jdx/mise/releases/download/v${MISE_VERSION}/mise-v${MISE_VERSION}-linux-$(uname -m | sed 's/x86_64/x64/;s/aarch64/arm64/').tar.xz" \
    | tar -xJf - -C /usr/local/bin --strip-components=2 mise/bin/mise

# set working directory
WORKDIR /app

# set the shell to bash
SHELL ["/bin/bash", "-c"]

# copy the mise configuration
COPY ../mise.toml /app/mise.toml

# trust the configuration and install dependencies
RUN mise trust && mise install

# add the mise shims directory to the PATH
ENV PATH="/root/.local/share/mise/shims:${PATH}"

# Supervisor belongs to the container, not the project: give it its own venv
# so /app/.venv (a volume, and pruned to the lockfile by `uv sync`) cannot hide
# it, and put that bin on PATH for init.sh.
RUN uv venv /opt/supervisor && uv pip install --python /opt/supervisor/bin/python supervisor
ENV PATH="/opt/supervisor/bin:${PATH}"

# create log directory for supervisor
RUN mkdir -p /var/log/supervisor

# copy supervisor configuration
COPY dev/supervisord.conf /etc/supervisor/supervisord.conf

# copy init script to root directory (won't be overwritten by volume mount)
COPY dev/init.sh /init.sh
RUN chmod +x /init.sh

# expose ports
EXPOSE 8000 5173

# start init script
CMD ["/init.sh"]
