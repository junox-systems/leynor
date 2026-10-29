from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomeRedirectTests(TestCase):
    def test_anonymous_goes_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, reverse("account_login"))

    def test_authed_goes_to_dashboard(self):
        user = get_user_model().objects.create_user(
            email="a@example.com", username="a", password="x"
        )
        self.client.force_login(user)
        self.assertRedirects(self.client.get("/"), reverse("dashboard"))


class RobotsTxtTests(TestCase):
    def test_serves_plain_text_without_sitemap(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertContains(response, "Disallow: /dashboard/")
        self.assertNotContains(response, "Sitemap:")


class RemovedPagesTests(TestCase):
    def test_terms_privacy_and_sitemap_are_gone(self):
        for path in ("/terms/", "/privacy/", "/sitemap.xml"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
