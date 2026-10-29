"""The app name is declared once and reaches every surface that shows it."""

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.users.models import User


def make_user():
    return User.objects.create_user(
        email="name@example.com", username="name", password="s3cret-pw"
    )


class AppNameTests(TestCase):
    def test_public_page_title_uses_the_configured_name(self):
        with override_settings(APP_NAME="Testify"):
            response = self.client.get(reverse("account_login"))
        self.assertContains(response, "Testify")

    def test_page_title_and_shell_use_the_configured_name(self):
        self.client.force_login(make_user())
        with override_settings(APP_NAME="Testify"):
            response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "<title>Dashboard — Testify</title>")

    def test_sidebar_payload_carries_the_name(self):
        self.client.force_login(make_user())
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["app_nav"]["name"], settings.APP_NAME)

    def test_queue_name_is_slug_plus_role(self):
        self.assertEqual(settings.Q_CLUSTER["name"], f"{settings.APP_SLUG}-default")
