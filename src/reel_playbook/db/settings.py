"""Django settings for the ORM layer only. The CLI is the web app's future consumer."""

import os
from urllib.parse import urlparse

DATABASE_URL = os.environ.get(
    "REEL_DB", "postgresql://postgres:postgres@127.0.0.1:5432/reel"
)
_url = urlparse(DATABASE_URL)

SECRET_KEY = "reel-playbook"
DEBUG = False
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = ["reel_playbook.db"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _url.path.lstrip("/") or "reel",
        "USER": _url.username or "postgres",
        "PASSWORD": _url.password or "",
        "HOST": _url.hostname or "127.0.0.1",
        "PORT": _url.port or 5432,
        "OPTIONS": {"connect_timeout": 5},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
