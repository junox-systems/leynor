from unittest import mock

from django.db import OperationalError
from django.test import TestCase


class HealthzTests(TestCase):
    def test_ok_when_db_reachable(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    @mock.patch(
        "apps.core.views.connection.ensure_connection",
        side_effect=OperationalError("down"),
    )
    def test_503_when_db_down(self, _):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 503)
