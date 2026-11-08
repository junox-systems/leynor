"""APP_SECRETS_KEY must be a Fernet key, and must be set outside development."""

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security)
def secrets_key_is_valid(app_configs, **kwargs):
    if not settings.APP_SECRETS_KEY:
        return []
    try:
        Fernet(settings.APP_SECRETS_KEY.encode())
    except ValueError:
        return [
            Error(
                "APP_SECRETS_KEY is not a Fernet key.",
                hint='Generate one: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"',
                id="ai.E001",
            )
        ]
    return []


@register(Tags.security, deploy=True)
def secrets_key_is_set(app_configs, **kwargs):
    if settings.APP_SECRETS_KEY:
        return []
    return [
        Warning(
            "APP_SECRETS_KEY is not set, so provider API keys are encrypted with a key derived from SECRET_KEY.",
            hint="Set APP_SECRETS_KEY to a Fernet key; rotating SECRET_KEY would otherwise make stored API keys unreadable.",
            id="ai.W001",
        )
    ]
