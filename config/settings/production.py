from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env, DMR_SETTINGS

from dmr.settings import Settings


def _required_list(name):
    values = [item.strip() for item in env.list(name, default=[]) if item.strip()]
    if not values:
        raise ImproperlyConfigured(f"{name} must be set in production.")
    return values


def _https_origins(name):
    origins = _required_list(name)
    insecure = [origin for origin in origins if not origin.startswith("https://")]
    if insecure:
        raise ImproperlyConfigured(
            f"{name} must list https origins, got: {', '.join(insecure)}"
        )
    return origins


# Performance: disable response validation in production.
# Docs: "Keep it on in development, but disable it in production
# to get the best of both worlds."
DMR_SETTINGS.update({Settings.validate_responses: False})

# Production-specific settings
# ------------------------------------------------------------------------------
DEBUG = False

# base.py falls back to a public dev key; never serve production with it.
if SECRET_KEY.startswith("django-insecure"):  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY must be set in production.")

# Required when DEBUG is off: a wildcard host defeats the point.
ALLOWED_HOSTS = _required_list("ALLOWED_HOSTS")
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must list real hostnames, never '*'.")

# Behind a TLS proxy Django sees http (until SECURE_PROXY_SSL_HEADER is on), so
# the browser's https Origin must be trusted explicitly or every POST gets 403.
CSRF_TRUSTED_ORIGINS = _https_origins("CSRF_TRUSTED_ORIGINS")

# Resend/SMTP providers reject unverified senders; the webmaster@localhost fallback would
# silently break signup (email verification is mandatory). No default on purpose.
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Security Settings
# ------------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Two kinds of warning are expected, not misconfigurations: the TLS settings
# below stay off until a deployment decides otherwise, and the Vite/staticfiles
# warnings only report missing build output, which a clean checkout has by
# definition. Silencing exactly those keeps `just check-deploy` a real gate:
# every other deployment warning still fails it.
SILENCED_SYSTEM_CHECKS = [
    "security.W004",
    "security.W008",
    "django_vite.W001",
    "staticfiles.W004",
]

# SSL/TLS: Enable these AFTER configuring your reverse proxy to set
# X-Forwarded-Proto. Do NOT enable without the proxy header — it
# causes infinite redirect loops. prod/nginx/nginx.conf (the nginx
# service in docker-stack.yml) sets the header.
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# SECURE_SSL_REDIRECT = True
# SECURE_HSTS_SECONDS = 31536000  # 1 year
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
