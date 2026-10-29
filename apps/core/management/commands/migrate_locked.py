from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

# Arbitrary app-wide constant; every container must use the same key.
LOCK_KEY = 0x6D696772  # "migr"


class Command(BaseCommand):
    help = "Run migrate under a Postgres advisory lock so concurrent containers queue."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            call_command("migrate", interactive=False)
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [LOCK_KEY])
            try:
                call_command("migrate", interactive=False)
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [LOCK_KEY])
