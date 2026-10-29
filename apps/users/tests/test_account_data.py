import json

from allauth.socialaccount.models import SocialAccount
from auditlog.models import LogEntry
from django.test import TestCase
from django.urls import reverse

from apps.orgs.models import Organization
from apps.users.models import User


class AccountDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="erin@example.com", username="erin", password="s3cret-pw"
        )
        SocialAccount.objects.create(
            user=self.user, provider="google", uid="g-1", extra_data={"t": "x"}
        )
        self.client.force_login(self.user)

    def reauth(self):
        self.client.post(reverse("account_reauthenticate"), {"password": "s3cret-pw"})

    def test_export_requires_reauthentication(self):
        response = self.client.get(reverse("export_data"))
        self.assertTrue(response.url.startswith(reverse("account_reauthenticate")))

    def test_export_contains_user_data_but_no_secrets(self):
        Organization.create_with_owner("Solo", self.user)
        self.reauth()
        response = self.client.get(reverse("export_data"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        data = json.loads(response.content)
        self.assertEqual(data["email"], "erin@example.com")
        self.assertEqual(
            data["social_accounts"], [{"provider": "google", "uid": "g-1"}]
        )
        self.assertNotIn("password", response.content.decode())
        self.assertNotIn("extra_data", data["social_accounts"][0])
        self.assertEqual(data["organizations"], [{"name": "Solo", "roles": ["owner"]}])

    def test_export_includes_mfa_devices_without_secrets(self):
        from allauth.mfa.models import Authenticator

        Authenticator.objects.create(
            user=self.user,
            type=Authenticator.Type.TOTP,
            data={"secret": "JBSWY3DPEHPK3PXP"},
        )
        self.reauth()
        response = self.client.get(reverse("export_data"))
        data = json.loads(response.content)
        self.assertEqual(data["mfa_authenticators"][0]["type"], "totp")
        self.assertNotIn("JBSWY3DPEHPK3PXP", response.content.decode())

    def test_delete_requires_matching_email(self):
        self.reauth()
        self.client.post(reverse("delete_account"), {"confirm": "wrong@example.com"})
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_removes_user_and_logs_out(self):
        Organization.create_with_owner("Solo", self.user)
        self.reauth()
        self.assertTrue(LogEntry.objects.filter(object_pk=str(self.user.pk)).exists())
        page = self.client.get(reverse("delete_account"))
        self.assertContains(page, 'name="confirm"')
        response = self.client.post(
            reverse("delete_account"), {"confirm": " Erin@Example.com "}
        )
        self.assertRedirects(response, reverse("home"))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Organization.objects.exists())
        self.assertFalse(LogEntry.objects.filter(object_pk=str(self.user.pk)).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_delete_post_requires_reauthentication(self):
        response = self.client.post(
            reverse("delete_account"), {"confirm": "erin@example.com"}
        )
        self.assertTrue(response.url.startswith(reverse("account_reauthenticate")))
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
