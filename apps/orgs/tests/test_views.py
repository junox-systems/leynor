from datetime import timedelta

from allauth.account.signals import user_signed_up
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import (
    ADMIN,
    INVITATION_TTL,
    MAX_PENDING_INVITATIONS,
    MEMBER,
    OWNER,
    Invitation,
    Membership,
    Organization,
    Role,
    release_user,
)
from apps.users.models import User

PASSWORD = "s3cret-pw"


def make_user(name):
    user = User.objects.create_user(
        email=f"{name}@example.com", username=name, password=PASSWORD
    )
    user.emailaddress_set.create(email=user.email, verified=True, primary=True)
    return user


def join(org, user, *role_names):
    membership = Membership.objects.create(organization=org, user=user)
    membership.roles.add(*Role.objects.filter(name__in=role_names))
    return membership


def role(name):
    return Role.objects.get(name=name)


class OrgTestCase(TestCase):
    def setUp(self):
        self.owner = make_user("olga")
        self.member = make_user("milo")
        self.outsider = make_user("otto")
        self.org = Organization.objects.create(name="Acme")
        self.owner_m = join(self.org, self.owner, OWNER)
        self.member_m = join(self.org, self.member, MEMBER)
        self.detail = reverse("org_detail", args=[self.org.pk])

    def login(self, user):
        # Log in and reauthenticate, so allauth's reauthentication gate passes.
        self.client.force_login(user)
        self.client.post(reverse("account_reauthenticate"), {"password": PASSWORD})


class OrgListTests(OrgTestCase):
    def test_empty_state(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("orgs"))
        self.assertContains(response, "not in any organization yet")

    def test_create_makes_requester_owner(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse("orgs"), {"name": "Globex"})
        org = Organization.objects.get(name="Globex")
        self.assertRedirects(response, reverse("org_detail", args=[org.pk]))
        self.assertTrue(org.memberships.get().is_owner)


class PersonalOrganizationTests(TestCase):
    def test_signup_creates_owned_workspace(self):
        user = make_user("sam")
        user_signed_up.send(sender=User, request=None, user=user)
        membership = user.memberships.get()
        self.assertEqual(membership.organization.name, "sam's workspace")
        self.assertTrue(membership.is_owner)

    def test_dashboard_shows_current_org(self):
        user = make_user("sam")
        user_signed_up.send(sender=User, request=None, user=user)
        self.client.force_login(user)
        payload = self.client.get(reverse("dashboard")).context["payload"]["org"]
        self.assertEqual(payload["org"]["name"], "sam's workspace")
        self.assertEqual(payload["org"]["roles"], [OWNER])

    def test_dashboard_empty_state_without_org(self):
        self.client.force_login(make_user("sam"))
        payload = self.client.get(reverse("dashboard")).context["payload"]["org"]
        self.assertIsNone(payload["org"])
        self.assertEqual(payload["urls"]["orgs"], reverse("orgs"))


class OrgSwitchTests(OrgTestCase):
    def test_switches_session_to_own_org(self):
        other = Organization.create_with_owner("Globex", self.member).organization
        self.client.force_login(self.member)
        self.client.get(self.detail)  # session now on Acme
        response = self.client.post(reverse("org_switch"), {"organization": other.pk})
        # Don't fetch: that would consume the flash message asserted below.
        self.assertRedirects(
            response, reverse("dashboard"), fetch_redirect_response=False
        )
        page = self.client.get(reverse("dashboard"))
        self.assertEqual(page.context["payload"]["org"]["org"]["name"], "Globex")
        self.assertContains(page, "Switched to Globex.")
        # Dashboard switcher lists both orgs with the current one selected.
        self.assertContains(page, 'id="org-switcher"')
        self.assertContains(page, f'data-value="{other.pk}" aria-selected="true"')
        self.assertContains(page, f'data-value="{self.org.pk}"')

    def test_switcher_hidden_with_one_org(self):
        self.client.force_login(self.member)
        self.assertNotContains(
            self.client.get(reverse("dashboard")), 'id="org-switcher"'
        )

    def test_rejects_foreign_and_malformed_ids(self):
        self.client.force_login(self.outsider)
        for value in (self.org.pk, "not-a-uuid"):
            response = self.client.post(reverse("org_switch"), {"organization": value})
            self.assertEqual(response.status_code, 404)


class OrgDetailTests(OrgTestCase):
    def test_non_member_gets_404(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.detail).status_code, 404)

    def test_owner_invites_by_email(self):
        self.client.force_login(self.owner)
        self.client.post(self.detail, {"email": " Otto@Example.com "})
        invitation = Invitation.objects.get(organization=self.org)
        self.assertEqual(invitation.email, "otto@example.com")
        self.assertEqual(mail.outbox[-1].to, ["otto@example.com"])
        self.assertIn(invitation.token, mail.outbox[-1].body)

    def test_member_cannot_invite_or_see_invitations(self):
        Invitation.objects.create(organization=self.org, email="x@example.com")
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.detail).context["invitations"], [])
        response = self.client.post(self.detail, {"email": "otto@example.com"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Invitation.objects.count(), 1)

    def test_inviting_existing_member_is_rejected(self):
        self.member.emailaddress_set.create(email="milo@work.example", verified=True)
        self.client.force_login(self.owner)
        for email in ("MILO@example.com", "milo@work.example"):
            response = self.client.post(self.detail, {"email": email})
            self.assertContains(response, "Already a member.")
        self.assertFalse(Invitation.objects.exists())

    def test_only_inviters_revoke_invitations(self):
        invitation = Invitation.objects.create(
            organization=self.org, email="x@example.com"
        )
        url = reverse("invitation_revoke", args=[self.org.pk, invitation.pk])
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.post(url), self.detail)
        self.assertFalse(Invitation.objects.exists())

    def test_promotion_applies_without_new_login(self):
        self.client.force_login(self.member)
        self.client.get(self.detail)  # RBAC session open as plain member
        self.assertEqual(
            self.client.post(self.detail, {"email": "o@example.com"}).status_code, 403
        )
        self.member_m.roles.add(role(ADMIN))
        response = self.client.post(self.detail, {"email": "o@example.com"})
        self.assertRedirects(response, self.detail)

    def test_pending_invitations_are_capped(self):
        Invitation.objects.bulk_create(
            Invitation(organization=self.org, email=f"p{i}@example.com", token=f"t{i}")
            for i in range(MAX_PENDING_INVITATIONS)
        )
        self.client.force_login(self.owner)
        response = self.client.post(self.detail, {"email": "otto@example.com"})
        self.assertContains(response, "pending invitations")
        self.assertFalse(Invitation.objects.filter(email="otto@example.com").exists())


class InvitationAcceptTests(OrgTestCase):
    def setUp(self):
        super().setUp()
        self.invitation = Invitation.objects.create(
            organization=self.org, email="otto@example.com", invited_by=self.owner
        )
        self.url = reverse("invitation_accept", args=[self.invitation.token])

    def test_matching_verified_email_joins_as_member(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url)
        self.assertRedirects(response, self.detail)
        joined = self.org.memberships.get(user=self.outsider)
        self.assertEqual([r.name for r in joined.roles.all()], [MEMBER])
        self.assertFalse(Invitation.objects.exists())

    def test_expired_invitation_is_refused(self):
        Invitation.objects.filter(pk=self.invitation.pk).update(
            created_at=timezone.now() - INVITATION_TTL - timedelta(minutes=1)
        )
        self.client.force_login(self.outsider)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "expired", status_code=410)
        self.assertFalse(self.org.memberships.filter(user=self.outsider).exists())

    def test_reinvite_rotates_token(self):
        self.client.force_login(self.owner)
        self.client.post(self.detail, {"email": "otto@example.com"})
        fresh = Invitation.objects.get(organization=self.org)
        self.assertNotEqual(fresh.token, self.invitation.token)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_other_account_cannot_use_token(self):
        self.client.force_login(make_user("eve"))
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.org.memberships.count(), 2)


class MembershipRemoveTests(OrgTestCase):
    def remove_url(self, membership, org=None):
        return reverse("membership_remove", args=[(org or self.org).pk, membership.pk])

    def test_member_can_leave_but_not_remove_others(self):
        self.client.force_login(self.member)
        response = self.client.post(self.remove_url(self.owner_m))
        self.assertEqual(response.status_code, 403)
        self.client.post(self.remove_url(self.member_m))
        self.assertFalse(Membership.objects.filter(pk=self.member_m.pk).exists())

    def test_last_owner_cannot_leave(self):
        self.client.force_login(self.owner)
        self.client.post(self.remove_url(self.owner_m))
        self.assertTrue(Membership.objects.filter(pk=self.owner_m.pk).exists())

    def test_admin_removes_members_but_not_owners(self):
        admin = join(self.org, make_user("ada"), ADMIN)
        self.client.force_login(admin.user)
        self.assertEqual(
            self.client.post(self.remove_url(self.owner_m)).status_code, 403
        )
        self.client.post(self.remove_url(self.member_m))
        self.assertFalse(Membership.objects.filter(pk=self.member_m.pk).exists())

    def test_membership_of_another_org_is_404(self):
        other = Organization.create_with_owner("Globex", self.outsider)
        self.client.force_login(self.owner)
        response = self.client.post(self.remove_url(other))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Membership.objects.filter(pk=other.pk).exists())


class OrgDeleteTests(OrgTestCase):
    def setUp(self):
        super().setUp()
        self.delete = reverse("org_delete", args=[self.org.pk])

    def test_member_cannot_delete(self):
        self.login(self.member)
        self.assertEqual(self.client.post(self.delete).status_code, 403)
        self.assertTrue(Organization.objects.exists())

    def test_owner_must_reauthenticate_then_delete_resumes(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.delete)
        self.assertTrue(response.url.startswith(reverse("account_reauthenticate")))
        self.assertTrue(Organization.objects.exists())
        # allauth suspended the POST; reauthenticating replays it.
        self.client.post(response.url, {"password": PASSWORD}, follow=True)
        self.assertFalse(Organization.objects.exists())

    def test_recently_authenticated_owner_deletes(self):
        self.login(self.owner)
        self.assertRedirects(self.client.post(self.delete), reverse("orgs"))
        self.assertFalse(Organization.objects.exists())


class MembershipRoleTests(OrgTestCase):
    def toggle(self, membership, role_name):
        return self.client.post(
            reverse("membership_role", args=[self.org.pk, membership.pk]),
            {"role": role(role_name).pk},
        )

    def toggle_follow(self, membership, role_name):
        return self.client.post(
            reverse("membership_role", args=[self.org.pk, membership.pk]),
            {"role": role(role_name).pk},
            follow=True,
        )

    def names(self, membership):
        return sorted(r.name for r in membership.roles.all())

    def test_owner_grants_and_revokes(self):
        self.client.force_login(self.owner)
        self.toggle(self.member_m, OWNER)
        self.assertEqual(self.names(self.member_m), [MEMBER, OWNER])
        # Stepping down: keep a role, then drop owner (another owner remains).
        self.toggle(self.owner_m, MEMBER)
        self.toggle(self.owner_m, OWNER)
        self.assertEqual(self.names(self.owner_m), [MEMBER])

    def test_members_last_role_cannot_be_revoked(self):
        self.client.force_login(self.owner)
        response = self.toggle_follow(self.member_m, MEMBER)
        self.assertContains(response, "at least one role")
        self.assertEqual(self.names(self.member_m), [MEMBER])

    def test_member_without_view_permission_gets_403(self):
        self.member_m.roles.set([])  # e.g. an operator emptied it in the admin
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.detail).status_code, 403)

    def test_member_cannot_change_roles(self):
        self.client.force_login(self.member)
        self.assertEqual(self.toggle(self.member_m, OWNER).status_code, 403)
        self.assertEqual(self.names(self.member_m), [MEMBER])

    def test_last_owner_keeps_owner_role(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("membership_role", args=[self.org.pk, self.owner_m.pk]),
            {"role": role(OWNER).pk},
            follow=True,
        )
        self.assertContains(response, "needs an owner")
        self.assertEqual(self.names(self.owner_m), [OWNER])

    def test_admin_grants_admin_but_not_owner(self):
        admin = join(self.org, make_user("ada"), ADMIN)
        self.client.force_login(admin.user)
        self.toggle(self.member_m, ADMIN)
        self.assertEqual(self.names(self.member_m), [ADMIN, MEMBER])
        self.assertEqual(self.toggle(self.member_m, OWNER).status_code, 403)
        self.assertEqual(self.toggle(self.owner_m, ADMIN).status_code, 403)

    def test_unknown_role_is_ignored(self):
        self.client.force_login(self.owner)
        url = reverse("membership_role", args=[self.org.pk, self.member_m.pk])
        for value in ("not-a-uuid", "0190f0f0-0000-7000-8000-000000000000"):
            self.assertRedirects(self.client.post(url, {"role": value}), self.detail)
        self.assertEqual(self.names(self.member_m), [MEMBER])


class ReleaseUserTests(OrgTestCase):
    def test_promotes_heir_and_deletes_solo_orgs(self):
        solo = Organization.create_with_owner("Solo", self.owner).organization
        release_user(self.owner)
        self.member_m.refresh_from_db()
        self.assertTrue(self.member_m.is_owner)
        self.assertFalse(Organization.objects.filter(pk=solo.pk).exists())


class RoleAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="root@example.com", username="root", password=PASSWORD
        )
        self.client.force_login(self.admin_user)

    def test_owner_role_cannot_be_deleted_in_admin(self):
        owner = role(OWNER)
        page = self.client.get(reverse("admin:orgs_role_delete", args=[owner.pk]))
        self.assertEqual(page.status_code, 403)
        self.client.post(
            reverse("admin:orgs_role_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [owner.pk, role(ADMIN).pk],
                "post": "yes",
            },
        )
        # The whole bulk delete is refused while owner is selected.
        self.assertEqual(Role.objects.filter(name__in=[OWNER, ADMIN]).count(), 2)

    def test_admin_rejects_hierarchy_cycle(self):
        member = role(MEMBER)
        response = self.client.post(
            reverse("admin:orgs_role_change", args=[member.pk]),
            {
                "name": "member",
                "description": member.description,
                "descendant": role(OWNER).pk,
                "permissions": [],
            },
        )
        self.assertContains(response, "cycle")
        member.refresh_from_db()
        self.assertIsNone(member.descendant)
