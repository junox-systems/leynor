import json

from auditlog.models import LogEntry
from django.test import TestCase
from django.urls import reverse

from apps.dashboard.panels import account_payload, activity_payload
from apps.users.models import User


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="s3cret-pw",
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def _login(self):
        return self.client.post(
            reverse("account_login"),
            {"login": "alice@example.com", "password": "s3cret-pw"},
        )

    def test_login_redirects_to_dashboard_once_email_verified(self):
        from allauth.account.models import EmailAddress

        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        self.assertEqual(reverse("dashboard"), "/dashboard/")
        self.assertRedirects(self._login(), reverse("dashboard"))

    def test_unverified_login_goes_to_verification_not_dashboard(self):
        # ACCOUNT_EMAIL_VERIFICATION = "mandatory" gates the dashboard behind
        # email confirmation — verify this stays true if that setting changes.
        response = self._login()
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, reverse("dashboard"))

    def test_login_honors_next_over_dashboard(self):
        from allauth.account.models import EmailAddress

        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        response = self.client.post(
            f"{reverse('account_login')}?next={reverse('profile')}",
            {"login": "alice@example.com", "password": "s3cret-pw"},
        )
        self.assertRedirects(response, reverse("profile"))

    def test_dashboard_renders_payload_as_json_script(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="dashboard-payload"')
        self.assertContains(
            response, 'data-svelte-bridge-component-value="dashboard/Dashboard"'
        )

        payload = response.context["payload"]
        self.assertEqual(set(payload), {"account", "org"})
        # Must survive a JSON round trip — it is rendered with json_script.
        json.dumps(payload)


class ActivityViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com", username="alice", password="s3cret-pw"
        )

    def test_requires_login(self):
        response = self.client.get(reverse("activity"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_renders_activity_island_in_app_shell(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("activity"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="activity-payload"')
        self.assertContains(
            response, 'data-svelte-bridge-component-value="dashboard/Activity"'
        )
        self.assertContains(response, 'hx-boost:inherited="true"')

        payload = response.context["payload"]
        self.assertEqual(set(payload), {"activity", "urls"})
        json.dumps(payload)
        self.assertEqual(payload["urls"]["activity"], reverse("dashboard-activity"))


class ActivityPayloadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com", username="alice", password="s3cret-pw"
        )
        self.other = User.objects.create_user(
            email="bob@example.com", username="bob", password="s3cret-pw"
        )

    def _log(self, actor, obj):
        return LogEntry.objects.log_create(
            obj,
            action=LogEntry.Action.UPDATE,
            changes={"username": ["old", "new"]},
            actor=actor,
        )

    def test_excludes_other_users_entries(self):
        self._log(self.user, self.user)
        self._log(self.other, self.other)

        entries = activity_payload(self.user)["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["object_repr"], str(self.user))

    def test_reports_field_names_not_values(self):
        self._log(self.user, self.user)
        entry = activity_payload(self.user)["entries"][0]
        self.assertEqual(entry["fields"], ["username"])
        # Values could be secrets (password hashes) — they must not leak.
        self.assertNotIn("old", json.dumps(entry))

    def test_respects_limit(self):
        for _ in range(3):
            self._log(self.user, self.user)
        self.assertEqual(len(activity_payload(self.user, limit=2)["entries"]), 2)

    def test_empty_for_user_with_no_activity(self):
        self.assertEqual(activity_payload(self.user)["entries"], [])


class AccountPayloadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com", username="alice", password="s3cret-pw"
        )

    def test_reports_unverified_email_and_no_providers(self):
        payload = account_payload(self.user)
        checks = {c["label"]: c for c in payload["checks"]}
        self.assertFalse(checks["Email verified"]["done"])
        self.assertFalse(checks["Connected accounts"]["done"])
        self.assertTrue(checks["Password set"]["done"])

    def test_reports_verified_email(self):
        from allauth.account.models import EmailAddress

        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        checks = {c["label"]: c for c in account_payload(self.user)["checks"]}
        self.assertTrue(checks["Email verified"]["done"])


class ProfileMovedUnderDashboardTests(TestCase):
    def test_profile_url_lives_under_dashboard(self):
        self.assertEqual(reverse("profile"), "/dashboard/user/profile/")

    def test_old_profile_url_is_gone(self):
        self.assertEqual(self.client.get("/profile/").status_code, 404)


class AppNavTests(TestCase):
    def _items(self, **user_fields):
        user = User.objects.create_user(
            email="nav@example.com", username="nav", password="s3cret-pw", **user_fields
        )
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        groups = response.context["app_nav"]["groups"]
        return response, [item for group in groups for item in group["items"]]

    def test_admin_link_only_for_staff_and_not_boosted(self):
        _, items = self._items()
        self.assertNotIn("Admin", [i["label"] for i in items])

        User.objects.all().delete()
        _, items = self._items(is_staff=True)
        admin = next(i for i in items if i["label"] == "Admin")
        self.assertIs(admin["boost"], False)

    def test_account_group_holds_activity_profile_and_orgs(self):
        response, _ = self._items()
        groups = {
            g["label"]: [i["label"] for i in g["items"]]
            for g in response.context["app_nav"]["groups"]
        }
        self.assertEqual(groups["Application"], ["Dashboard"])
        self.assertEqual(
            groups["Account"][:3], ["Activity", "Profile", "Organizations"]
        )

    def test_sidebar_is_preserved_across_boosted_visits(self):
        response, _ = self._items()
        self.assertContains(response, 'hx-boost:inherited="true"')
        self.assertContains(response, "hx-preserve")


class DashboardActivityAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com", username="alice", password="s3cret-pw"
        )

    def test_requires_authentication(self):
        response = self.client.get(reverse("dashboard-activity"))
        self.assertIn(response.status_code, (401, 403))

    def test_returns_entries_for_authenticated_user(self):
        LogEntry.objects.log_create(
            self.user,
            action=LogEntry.Action.UPDATE,
            changes={"username": ["old", "new"]},
            actor=self.user,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard-activity"))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["fields"], ["username"])
