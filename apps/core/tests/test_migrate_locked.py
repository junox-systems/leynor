from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

CMD = "apps.core.management.commands.migrate_locked"


class MigrateLockedTests(SimpleTestCase):
    @mock.patch(f"{CMD}.call_command")
    def test_runs_plain_migrate_off_postgres(self, migrate):
        call_command("migrate_locked")
        migrate.assert_called_once_with("migrate", interactive=False)

    @mock.patch(f"{CMD}.call_command")
    @mock.patch(f"{CMD}.connection")
    def test_wraps_migrate_in_advisory_lock_on_postgres(self, connection, migrate):
        connection.vendor = "postgresql"
        cursor = connection.cursor.return_value.__enter__.return_value
        migrate.side_effect = RuntimeError("migration failed")

        with self.assertRaises(RuntimeError):
            call_command("migrate_locked")

        sql = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertEqual(
            sql, ["SELECT pg_advisory_lock(%s)", "SELECT pg_advisory_unlock(%s)"]
        )
