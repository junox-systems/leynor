import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


PROD_ENV = {
    "SECRET_KEY": "a-real-key",
    "DEFAULT_FROM_EMAIL": "hello@example.com",
    "ALLOWED_HOSTS": "example.com",
    "CSRF_TRUSTED_ORIGINS": "https://example.com",
}


def load_settings(module, expr="s.AWS_S3_CUSTOM_DOMAIN", **env):
    """Import a settings module in a fresh interpreter; settings are module-level."""
    return subprocess.run(
        [sys.executable, "-c", f"import {module} as s; print({expr})"],
        cwd=settings.BASE_DIR,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
    )


def load_production(**overrides):
    """Import production settings; a None value leaves that variable unset."""
    env = {**os.environ, **PROD_ENV}
    for name, value in overrides.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value

    return subprocess.run(
        [sys.executable, "-c", "import config.settings.production"],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


class ProductionSecretKeyTests(SimpleTestCase):
    def test_refuses_dev_default_key(self):
        result = load_production(SECRET_KEY="django-insecure-whatever")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY must be set in production", result.stderr)

    def test_accepts_complete_config(self):
        result = load_production()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_requires_from_email(self):
        result = load_production(DEFAULT_FROM_EMAIL=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEFAULT_FROM_EMAIL", result.stderr)


class ProductionHostTests(SimpleTestCase):
    def test_requires_allowed_hosts(self):
        for hosts in (None, ""):
            with self.subTest(hosts=hosts):
                result = load_production(ALLOWED_HOSTS=hosts)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ALLOWED_HOSTS must be set", result.stderr)

    def test_refuses_wildcard_host(self):
        for hosts in ("*", "example.com,*"):
            with self.subTest(hosts=hosts):
                result = load_production(ALLOWED_HOSTS=hosts)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("never '*'", result.stderr)

    def test_requires_csrf_origins(self):
        result = load_production(CSRF_TRUSTED_ORIGINS=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CSRF_TRUSTED_ORIGINS must be set", result.stderr)

    def test_refuses_insecure_csrf_origin(self):
        result = load_production(CSRF_TRUSTED_ORIGINS="http://example.com")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("http://example.com", result.stderr)


class StorageBackendTests(SimpleTestCase):
    expr = 's.STORAGES["default"]["BACKEND"]'
    FULL_S3 = {
        "AWS_ACCESS_KEY_ID": "key",
        "AWS_SECRET_ACCESS_KEY": "secret",
        "AWS_STORAGE_BUCKET_NAME": "media",
    }

    def backend(self, **env):
        result = load_settings("config.settings.base", self.expr, **env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_local_disk_by_default(self):
        self.assertEqual(
            self.backend(AWS_ACCESS_KEY_ID="", AWS_STORAGE_BUCKET_NAME=""),
            "django.core.files.storage.FileSystemStorage",
        )

    def test_complete_s3_config_selects_s3(self):
        self.assertEqual(
            self.backend(**self.FULL_S3), "apps.core.storage.PublicEndpointS3Storage"
        )

    def test_storage_backend_overrides_auto_detection(self):
        for name, backend in {
            "local": "django.core.files.storage.FileSystemStorage",
            "azure": "storages.backends.azure_storage.AzureStorage",
            "gcs": "storages.backends.gcloud.GoogleCloudStorage",
        }.items():
            with self.subTest(backend=name):
                self.assertEqual(
                    self.backend(STORAGE_BACKEND=name, **self.FULL_S3), backend
                )

    def test_unknown_storage_backend_refuses_to_start(self):
        result = load_settings("config.settings.base", STORAGE_BACKEND="dropbox")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STORAGE_BACKEND='dropbox'", result.stderr)


class S3CustomDomainTests(SimpleTestCase):
    def test_custom_endpoint_drops_amazonaws_domain(self):
        result = load_settings(
            "config.settings.base",
            AWS_S3_ENDPOINT_URL="http://s3:9000",
            AWS_STORAGE_BUCKET_NAME="media",
        )
        self.assertEqual(result.stdout.strip(), "None", result.stderr)

    def test_real_aws_uses_bucket_domain(self):
        result = load_settings(
            "config.settings.base",
            AWS_S3_ENDPOINT_URL="",
            AWS_STORAGE_BUCKET_NAME="media",
        )
        self.assertEqual(result.stdout.strip(), "media.s3.amazonaws.com", result.stderr)


class EmailBackendTests(SimpleTestCase):
    expr = "s.EMAIL_BACKEND, getattr(s, 'EMAIL_HOST', None)"

    def test_resend_key_selects_resend(self):
        result = load_settings(
            "config.settings.base", self.expr, RESEND_API_KEY="re_x", EMAIL_URL=""
        )
        self.assertIn(
            "anymail.backends.resend.EmailBackend", result.stdout, result.stderr
        )

    def test_email_url_configures_smtp(self):
        result = load_settings(
            "config.settings.base",
            self.expr,
            RESEND_API_KEY="",
            EMAIL_URL="smtp+tls://u:p@smtp.example.com:587",
        )
        self.assertEqual(
            result.stdout.strip(),
            "django.core.mail.backends.smtp.EmailBackend smtp.example.com",
            result.stderr,
        )

    def test_empty_email_url_falls_back_to_localhost(self):
        result = load_settings(
            "config.settings.base", self.expr, RESEND_API_KEY="", EMAIL_URL=""
        )
        self.assertEqual(
            result.stdout.strip(),
            "django.core.mail.backends.smtp.EmailBackend localhost",
            result.stderr,
        )
