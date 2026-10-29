### config/settings/base.py

import logging
import os
import re
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# Initialize django-environ with default values
env = environ.Env(
    DEBUG=(bool, False),
    ENVIRONMENT=(str, "development"),
    SECRET_KEY=(str, "django-insecure-development-key-for-local-use-only"),
    ALLOWED_HOSTS=(list, []),
    DATABASE_URL=(str, "postgresql://postgres:postgres@db:5432/db"),
    AWS_ACCESS_KEY_ID=(str, ""),
    AWS_SECRET_ACCESS_KEY=(str, ""),
    AWS_STORAGE_BUCKET_NAME=(str, ""),
    STORAGE_BACKEND=(str, ""),
    RESEND_API_KEY=(str, ""),
    SENTRY_DSN=(str, ""),
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read .env file if it exists
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Core Settings
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# Application definition
INSTALLED_APPS = [
    # Local Apps
    "apps.core",
    "apps.users",
    "apps.api",
    "apps.pages",
    "apps.dashboard",
    "apps.orgs",
    # Django Built-in
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    # Default widget templates for FORM_RENDERER below.
    "django.forms",
    # Third Party
    # DJ Control Room — shared core lib first, then panels, then control room
    # (so all panels appear under one "DJ Control Room" section in admin)
    "dj_control_room_base",
    "dj_cache_panel",
    "dj_urls_panel",
    "dj_signals_panel",
    "dj_control_room",
    "django_q",
    "constance",
    "import_export",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.apple",
    "allauth.socialaccount.providers.microsoft",
    "dmr",
    "corsheaders",
    "django_vite",
    # Cotton: <c-*> template components. SimpleAppConfig = loaders wired below by hand,
    # because the auto config would overwrite dev.py's uncached loaders.
    "django_cotton.apps.SimpleAppConfig",
    "imagekit",
    "anymail",
    # paradedb_* diagnostic management commands
    "paradedb",
    "auditlog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Whitenoise
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # CORS
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # Allauth
    "auditlog.middleware.AuditlogMiddleware",
]

# Django Modern REST (DMR) Settings
# ------------------------------------------------------------------------------
from dmr.settings import Settings  # noqa: E402
from dmr.openapi import OpenAPIConfig  # noqa: E402

DMR_SETTINGS: dict = {
    Settings.openapi_config: OpenAPIConfig(
        title="Django Starter Kit API",
        version="0.1.0",
    ),
}

ROOT_URLCONF = "config.urls"

ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            # Cotton compiles <c-*> tags first; cached in prod/test, uncached in dev.py.
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django_cotton.cotton_loader.Loader",
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                )
            ],
            "builtins": ["django_cotton.templatetags.cotton"],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.dashboard.context_processors.app_nav",
                "apps.orgs.context_processors.current_org",
            ],
        },
    },
]

# Widgets render through TEMPLATES above (Cotton included), so a widget template
# can compose Cotton components, e.g. users/widgets/avatar_input.html.
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# Database
DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgresql://postgres:postgres@db:5432/db"
    ),
}
DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
# For psycopg 3 connection recycling strategy (uncomment when needed):
# DATABASES["default"]["CONN_MAX_AGE_STRATEGY"] = "max_lifetime"

# Authentication
AUTH_USER_MODEL = "users.User"
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)
# Declared explicitly — LoginRequiredMixin depends on it, and Django's default
# only happened to match allauth's mount point by coincidence.
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/dashboard/"
# Logging out lands on the public marketing page, not the app.
LOGOUT_REDIRECT_URL = "/"
ACCOUNT_ADAPTER = "apps.users.adapter.AccountAdapter"
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# ------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # For production 'collectstatic'
STATICFILES_DIRS = [
    BASE_DIR / "frontend/dist",  # Vite build output
]


# http://whitenoise.evans.io/en/stable/django.html#WHITENOISE_IMMUTABLE_FILE_TEST
def immutable_file_test(path, url):
    # Match vite (rollup)-generated hashes, à la, `some_file-CSliV9zW.js`
    return re.match(r"^.+[.-][0-9a-zA-Z_-]{8,}\..+$", url)


WHITENOISE_IMMUTABLE_FILE_TEST = immutable_file_test

# Django-Vite Settings
# ------------------------------------------------------------------------------
DJANGO_VITE = {
    "default": {
        "dev_mode": True if env("ENVIRONMENT") == "development" else False,
        "dev_server_host": "localhost",
        "dev_server_port": 5173,
    }
}

# Media files (User uploads)
# ------------------------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# S3 Storage Settings
# ------------------------------------------------------------------------------
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="")
# Browser-facing endpoint when AWS_S3_ENDPOINT_URL is internal (e.g. a private
# network address). Empty means URLs are signed against AWS_S3_ENDPOINT_URL.
AWS_S3_PUBLIC_ENDPOINT_URL = env("AWS_S3_PUBLIC_ENDPOINT_URL", default="")
# Only for real AWS: with a custom endpoint (R2, MinIO) boto must build
# URLs from AWS_S3_ENDPOINT_URL, or media links point at amazonaws.com.
AWS_S3_CUSTOM_DOMAIN = (
    None if AWS_S3_ENDPOINT_URL else f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
)
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}
AWS_LOCATION = "static"
# STATIC_URL is already defined above, this is for S3 static files
# STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # Compressed, NOT Manifest. Vite already content-hashes everything it
        # emits, and WHITENOISE_IMMUTABLE_FILE_TEST above matches those hashes
        # for far-future caching — so Django re-hashing them is redundant work
        # whose only real effect is a failure mode: the manifest post-processor
        # rewrites `//# sourceMappingURL=` comments and hard-fails collectstatic
        # when a referenced .map does not exist. Bundled deps embed exactly that
        # (rrweb ships a blob-worker source-map comment), and whether it trips
        # depends on where the minifier happened to put a newline, because
        # Django's pattern is line-anchored. Deployment must not be that fragile.
        # Trade-off: non-Vite assets (admin, dj-control-room) are served
        # unhashed, so they get whitenoise's short max-age instead of immutable.
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Media storage: one Storage API for every backend, so fields, imagekit and
# templates never learn where bytes live. Local disk unless told otherwise;
# with no STORAGE_BACKEND, complete AWS_* config means s3.
# azure/gcs need their extra: `uv add "django-storages[azure]"` (or [google]).
STORAGE_BACKENDS = {
    "local": "django.core.files.storage.FileSystemStorage",
    "s3": "apps.core.storage.PublicEndpointS3Storage",
    "azure": "storages.backends.azure_storage.AzureStorage",
    "gcs": "storages.backends.gcloud.GoogleCloudStorage",
}
_S3_CONFIGURED = bool(
    AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME
)
STORAGE_BACKEND = env("STORAGE_BACKEND") or ("s3" if _S3_CONFIGURED else "local")

if STORAGE_BACKEND not in STORAGE_BACKENDS:
    raise ImproperlyConfigured(
        f"STORAGE_BACKEND={STORAGE_BACKEND!r} is not one of "
        f"{', '.join(STORAGE_BACKENDS)}."
    )

STORAGES["default"] = {"BACKEND": STORAGE_BACKENDS[STORAGE_BACKEND]}

if STORAGE_BACKEND == "s3":
    STORAGES["default"]["OPTIONS"] = {
        "public_endpoint_url": AWS_S3_PUBLIC_ENDPOINT_URL or None
    }
elif not _S3_CONFIGURED:
    _aws_vars_set = sum(
        [
            1
            for v in [AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME]
            if v
        ]
    )
    if _aws_vars_set not in (0, 3):
        logger.warning(
            "Ignoring partial S3 config (%d of 3 vars set); media stay local.",
            _aws_vars_set,
        )

# Email
# ------------------------------------------------------------------------------
# Resend API when RESEND_API_KEY is set, else any SMTP server via EMAIL_URL
# (smtp+tls://user:pass@host:587, smtp+ssl://…:465).
if env("RESEND_API_KEY"):
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
else:
    # `or`: the stack passes EMAIL_URL="" when unset, which environ can't parse.
    _email_url = env("EMAIL_URL", default="") or "smtp://localhost:25"
    vars().update(env.email_url_config(_email_url))

# Cache
# ------------------------------------------------------------------------------
CACHES = {
    "default": {
        # Postgres-backed: no Redis. Table created by apps/core migration 0001.
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

# django-constance defaults to its Redis backend; keep settings in Postgres.
CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

# django-q2
# ------------------------------------------------------------------------------
# The ORM is the broker: tasks queue in Postgres, no Redis. Run workers with
# `python manage.py qcluster`; schedules live in the admin (django_q.Schedule).
Q_CLUSTER = {
    "name": "django-starter-kit",
    "orm": "default",
    "workers": 2,
    "timeout": 25 * 60,  # seconds, hard limit per task
    "retry": 30 * 60,  # re-queue tasks not acknowledged by then; must exceed timeout
    "max_attempts": 5,
    "catch_up": False,  # skip schedules missed while the cluster was down
}

# Anymail
# ------------------------------------------------------------------------------
ANYMAIL = {
    "RESEND_API_KEY": env("RESEND_API_KEY"),
}

# Sentry
# ------------------------------------------------------------------------------
_sentry_dsn = env("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[
            DjangoIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

# ------------------------------------------------------------------------------

# ImageKit
# ------------------------------------------------------------------------------
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = "imagekit.cachefiles.strategies.Optimistic"

# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
