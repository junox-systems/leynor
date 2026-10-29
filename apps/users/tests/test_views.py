from django.test import TestCase
from django.urls import reverse

from apps.users.models import User


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="s3cret-pw",
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_profile_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alice@example.com")
        self.assertContains(response, "@alice")
        self.assertContains(response, "Change Password")


class AllauthPagesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="s3cret-pw",
        )

    def test_public_account_pages_render(self):
        urls = [
            reverse("account_login"),
            reverse("account_signup"),
            reverse("account_reset_password"),
            reverse("account_reset_password_done"),
            reverse("account_email_verification_sent"),
            reverse("account_inactive"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'hx-boost:inherited="true"')
                self.assertNotContains(response, "app/Sidebar")

    def test_invalid_confirm_and_reset_links_render(self):
        for url in (
            reverse("account_confirm_email", args=["invalid-key"]),
            reverse(
                "account_reset_password_from_key",
                args=["invalid-uidb36", "invalid-key"],
            ),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_authenticated_management_pages_render(self):
        self.client.force_login(self.user)
        urls = [
            reverse("account_change_password"),
            reverse("account_email"),
            reverse("account_reauthenticate"),
            reverse("socialaccount_connections"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'hx-boost:inherited="true"')
                self.assertContains(
                    response, 'data-svelte-bridge-component-value="app/Sidebar"'
                )
                self.assertContains(response, 'id="app-nav-data"')

    def test_set_password_page_renders_for_passwordless_user(self):
        # allauth only renders /accounts/password/set/ for users without a
        # usable password; everyone else is redirected to the change view.
        passwordless = User.objects.create_user(
            email="carol@example.com",
            username="carol",
        )
        self.client.force_login(passwordless)
        response = self.client.get(reverse("account_set_password"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-boost:inherited="true"')
        self.assertContains(
            response, 'data-svelte-bridge-component-value="app/Sidebar"'
        )
        self.assertContains(response, 'id="app-nav-data"')

    def test_connected_accounts_render_in_connections_page(self):
        from allauth.socialaccount.models import SocialAccount

        account = SocialAccount.objects.create(
            user=self.user, provider="google", uid="g-12345"
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("socialaccount_connections"))
        self.assertEqual(response.status_code, 200)
        # The radio carries the real account pk (no phantom "" empty-label
        # choice from the form field's ModelChoiceField), and the radio loop
        # renders one row per connected account.
        self.assertContains(response, f'name="account" value="{account.pk}"')
        self.assertNotContains(response, 'name="account" value=""')


class SignupWelcomeEmailTests(TestCase):
    def test_signup_queues_welcome_email(self):
        from django.core import mail

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("account_signup"),
                {
                    "email": "new@example.com",
                    "username": "newbie",
                    "password1": "a-long-s3cret-pw",
                    "password2": "a-long-s3cret-pw",
                },
            )
        subjects = [m.subject for m in mail.outbox]
        self.assertIn("Welcome aboard", subjects)
