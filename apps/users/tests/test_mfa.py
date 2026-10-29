from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from django.test import TestCase
from django.urls import reverse

from apps.users.models import User


class MfaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="dana@example.com", username="dana", password="s3cret-pw"
        )
        self.user.emailaddress_set.create(
            email=self.user.email, verified=True, primary=True
        )

    def test_index_renders_in_app_shell(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("mfa_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-boost:inherited="true"')
        self.assertContains(response, "Authenticator App")
        self.assertContains(response, 'class="btn"')

    def test_login_with_totp_requires_second_step(self):
        TOTP.activate(self.user, generate_totp_secret())
        response = self.client.post(
            reverse("account_login"),
            {"login": "dana@example.com", "password": "s3cret-pw"},
        )
        self.assertRedirects(response, reverse("mfa_authenticate"))
        self.assertNotIn("_auth_user_id", self.client.session)

        page = self.client.get(reverse("mfa_authenticate"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="code"')
        self.assertContains(page, 'class="field')

    def test_activate_totp_page_renders_after_reauthentication(self):
        self.client.force_login(self.user)
        gate = self.client.get(reverse("mfa_activate_totp"))
        self.assertTrue(gate.url.startswith(reverse("account_reauthenticate")))

        self.client.post(reverse("account_reauthenticate"), {"password": "s3cret-pw"})
        response = self.client.get(reverse("mfa_activate_totp"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-boost:inherited="true"')
        self.assertContains(response, 'name="code"')
        # QR SVG is black-on-transparent; needs a white plate to show in dark mode.
        self.assertContains(response, "rounded-md bg-white p-3")
