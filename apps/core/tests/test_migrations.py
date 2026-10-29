import os
import subprocess
import sys
import tempfile

from django.conf import settings
from django.test import SimpleTestCase


class MissingMigrationTests(SimpleTestCase):
    def test_every_model_change_has_a_migration(self):
        # Test settings disable migrations, so this runs in a fresh interpreter.
        # SQLite keeps it from warning about an unreachable database server.
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
                cwd=settings.BASE_DIR,
                env={
                    **os.environ,
                    "DJANGO_SETTINGS_MODULE": "config.settings.dev",
                    "DATABASE_URL": f"sqlite:///{tmp}/check.db",
                },
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
