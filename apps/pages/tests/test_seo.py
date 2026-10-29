from django.test import TestCase
from django.urls import reverse


class RobotsTxtTests(TestCase):
    def test_serves_plain_text_pointing_at_sitemap(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertContains(response, "Disallow: /dashboard/")
        self.assertContains(response, "Sitemap: http://testserver/sitemap.xml")


class SitemapTests(TestCase):
    def test_lists_home_page(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"<loc>http://testserver{reverse('home')}</loc>")


class LegalPagesTests(TestCase):
    def test_pages_render_and_are_linked_from_signup(self):
        for name in ("terms", "privacy"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        signup = self.client.get(reverse("account_signup"))
        self.assertContains(signup, f'href="{reverse("terms")}"')
        self.assertContains(signup, f'href="{reverse("privacy")}"')

    def test_listed_in_sitemap(self):
        response = self.client.get("/sitemap.xml")
        self.assertContains(response, f"http://testserver{reverse('privacy')}</loc>")
