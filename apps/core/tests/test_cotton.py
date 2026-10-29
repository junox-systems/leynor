from django.contrib import messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.orgs.models import Organization
from apps.users.models import User


class CottonPagesTests(TestCase):
    """Every page built from Cotton components renders, with no <c-*> tag left uncompiled."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="dana@example.com", username="dana", password="s3cret-pw"
        )

    def assertCompiled(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<c-")
        return response

    def test_public_pages(self):
        for name in ("home", "account_login", "account_signup", "account_inactive"):
            with self.subTest(name=name):
                self.assertCompiled(reverse(name))

    def test_app_pages(self):
        self.client.force_login(self.user)
        self.client.post(reverse("orgs"), {"name": "Acme"})
        org = Organization.objects.get(name="Acme")
        for url in (
            reverse("profile"),
            reverse("delete_account"),
            reverse("orgs"),
            reverse("org_detail", args=[org.pk]),
            reverse("account_email"),
            reverse("mfa_index"),
        ):
            with self.subTest(url=url):
                self.assertCompiled(url)

    def test_form_errors_render_through_fields_component(self):
        response = self.client.post(
            reverse("account_login"), {"login": "dana@example.com", "password": "wrong"}
        )
        self.assertContains(response, 'data-variant="destructive" role="alert"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')


class MessagesToastTests(TestCase):
    """Django messages render as Basecoat toasts, escaped, one category per level."""

    def render(self, *pairs):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(request)
        request._messages = FallbackStorage(request)
        for level, text in pairs:
            messages.add_message(request, level, text, extra_tags="extra")
        return render_to_string("cotton/messages.html", request=request)

    def test_categories_and_persistence(self):
        html = self.render(
            (messages.SUCCESS, "Saved."),
            (messages.ERROR, "Nope."),
            (messages.WARNING, "Careful."),
        )
        self.assertIn('id="toaster"', html)
        self.assertNotIn("<c-", html)
        self.assertInHTML(
            '<div class="toast" role="status" aria-atomic="true" data-category="success">'
            '<div class="toast-content">'
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-circle-check" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="m9 12 2 2 4-4" /></svg>'
            "<section><h2>Saved.</h2></section></div></div>",
            html,
        )
        # Errors announce assertively; errors + warnings stay until dismissed,
        # and level_tag ignores extra_tags.
        self.assertRegex(
            html,
            r'role="alert"\s+aria-atomic="true"\s+data-category="error"\s+data-duration="-1"',
        )
        self.assertRegex(
            html,
            r'role="status"\s+aria-atomic="true"\s+data-category="warning"\s+data-duration="-1"',
        )
        self.assertEqual(html.count("data-toast-cancel"), 2)

    def test_escapes_message_text(self):
        html = self.render((messages.SUCCESS, "<b>bold</b>"))
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", html)
        self.assertNotIn("<b>bold</b>", html)

    def test_no_messages_empty_toaster(self):
        html = self.render()
        self.assertIn('id="toaster"', html)
        self.assertNotIn("<template", html)
