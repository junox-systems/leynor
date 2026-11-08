"""A text column stored encrypted at rest (Fernet), read back as plain text."""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

log = logging.getLogger(__name__)


def secrets_key() -> bytes:
    """APP_SECRETS_KEY, or (development only) a key derived from SECRET_KEY."""
    if settings.APP_SECRETS_KEY:
        return settings.APP_SECRETS_KEY.encode()
    digest = hashlib.sha256(f"leynor-secrets:{settings.SECRET_KEY}".encode()).digest()
    return base64.urlsafe_b64encode(digest)


def fernet() -> Fernet:
    return Fernet(secrets_key())


class EncryptedTextField(models.TextField):
    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value:
            return ""
        return fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return ""
        try:
            return fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # The secrets key changed: the value is unreadable, not wrong. Treat
            # it as unset so the admin can enter it again.
            log.warning("%s: stored secret cannot be decrypted with APP_SECRETS_KEY", self)
            return ""
