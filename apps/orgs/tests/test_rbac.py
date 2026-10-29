"""The functional specification of ANSI INCITS 359-2004, one test class per section."""

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from apps.orgs import rbac
from apps.orgs.models import ADMIN, MEMBER, OWNER, Membership, Organization, Role
from apps.users.models import User


def request_for(user, session=None):
    """A fresh request (new per HTTP call) sharing one Django session."""
    request = RequestFactory().get("/")
    request.user = user or AnonymousUser()
    request.session = session if session is not None else SessionStore()
    return request


def role(name):
    return Role.objects.get(name=name)


class RBACTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com", username="alice"
        )
        self.bob = User.objects.create_user(email="bob@example.com", username="bob")
        self.acme = Organization.create_with_owner("Acme", self.alice)
        self.org = self.acme.organization
        self.bob_m = Membership.objects.create(organization=self.org, user=self.bob)
        rbac.assign_user(self.bob_m, role(MEMBER))


class DefaultRoleTests(RBACTestCase):
    def test_limited_hierarchy_owner_admin_member(self):
        self.assertEqual(
            [r.name for r in role(OWNER).juniors()], [OWNER, ADMIN, MEMBER]
        )
        self.assertIsNone(role(MEMBER).descendant)

    def test_seed_is_idempotent_and_keeps_edits(self):
        rbac.revoke_permission(role(ADMIN), "orgs.invite_member")
        rbac.seed_default_roles(sender=Organization._meta.app_config)
        self.assertEqual(Role.objects.count(), 3)
        self.assertNotIn("orgs.invite_member", rbac.role_permissions(role(ADMIN)))


class CoreAdministrativeCommandTests(RBACTestCase):
    """§6.1.1"""

    def test_add_role_requires_new_name(self):
        auditor = rbac.add_role("auditor", "Reads everything.")
        self.assertEqual(rbac.role_permissions(auditor), set())
        with self.assertRaises(rbac.RBACError):
            rbac.add_role("auditor")

    def test_delete_role_removes_ua_and_pa(self):
        auditor = rbac.add_role("auditor")
        rbac.grant_permission(auditor, "orgs.view_organization")
        rbac.assign_user(self.bob_m, auditor)
        rbac.delete_role(auditor)
        self.assertEqual([r.name for r in self.bob_m.roles.all()], [MEMBER])

    def test_owner_role_cannot_be_deleted(self):
        with self.assertRaises(rbac.RBACError):
            rbac.delete_role(role(OWNER))

    def test_assign_and_deassign_validity(self):
        with self.assertRaises(rbac.RBACError):
            rbac.assign_user(self.bob_m, role(MEMBER))  # already assigned
        rbac.assign_user(self.bob_m, role(ADMIN))
        rbac.deassign_user(self.bob_m, role(MEMBER))
        with self.assertRaises(rbac.RBACError):
            rbac.deassign_user(self.bob_m, role(MEMBER))  # no longer assigned

    def test_member_keeps_at_least_one_role(self):
        with self.assertRaisesMessage(rbac.RBACError, "at least one role"):
            rbac.deassign_user(self.bob_m, role(MEMBER))
        self.assertEqual([r.name for r in self.bob_m.roles.all()], [MEMBER])

    def test_last_owner_cannot_be_deassigned(self):
        rbac.assign_user(self.acme, role(MEMBER))
        with self.assertRaisesMessage(ValidationError, "needs an owner"):
            rbac.deassign_user(self.acme, role(OWNER))
        rbac.assign_user(self.bob_m, role(OWNER))
        rbac.deassign_user(self.acme, role(OWNER))  # bob still owns it

    def test_grant_and_revoke_permission(self):
        rbac.grant_permission(role(MEMBER), "orgs.invite_member")
        self.assertIn("orgs.invite_member", rbac.role_permissions(role(MEMBER)))
        rbac.revoke_permission(role(MEMBER), "orgs.invite_member")
        with self.assertRaises(rbac.RBACError):
            rbac.revoke_permission(role(MEMBER), "orgs.invite_member")
        with self.assertRaises(rbac.RBACError):
            rbac.grant_permission(role(MEMBER), "orgs.no_such_operation")


class LimitedHierarchyCommandTests(RBACTestCase):
    """§6.2.2.1 (and §6.2.1.1 AddAscendant / AddDescendant / DeleteInheritance)"""

    def test_add_inheritance_rejects_second_descendant(self):
        auditor = rbac.add_role("auditor")
        with self.assertRaises(rbac.RBACError):
            rbac.add_inheritance(role(ADMIN), auditor)  # admin already inherits member

    def test_add_inheritance_rejects_cycles(self):
        with self.assertRaises(rbac.RBACError):
            rbac.add_inheritance(role(MEMBER), role(OWNER))
        with self.assertRaises(rbac.RBACError):
            rbac.add_inheritance(role(MEMBER), role(MEMBER))

    def test_role_clean_rejects_cycles_from_admin(self):
        member = role(MEMBER)
        member.descendant = role(OWNER)
        with self.assertRaises(ValidationError):
            member.clean()

    def test_ascendant_inherits_descendant_permissions(self):
        lead = rbac.add_ascendant("lead", role(MEMBER))
        self.assertIn("orgs.view_organization", rbac.role_permissions(lead))
        intern = rbac.add_descendant(rbac.add_role("trainee"), "intern")
        rbac.grant_permission(intern, "orgs.view_organization")
        self.assertIn("orgs.view_organization", rbac.role_permissions(role("trainee")))

    def test_delete_inheritance_recomputes_closure(self):
        rbac.delete_inheritance(role(ADMIN), role(MEMBER))
        self.assertNotIn("orgs.view_organization", rbac.role_permissions(role(OWNER)))
        with self.assertRaises(rbac.RBACError):
            rbac.delete_inheritance(role(OWNER), role(MEMBER))  # not immediate


class SessionFunctionTests(RBACTestCase):
    """§6.1.2 / §6.2.1.2"""

    def test_create_session_activates_authorized_roles(self):
        request = request_for(self.alice)
        session = rbac.create_session(request, self.acme)
        self.assertEqual({r.name for r in session.roles}, {OWNER, ADMIN, MEMBER})
        self.assertTrue(rbac.check_access(request, "orgs.view_organization", self.org))

    def test_create_session_rejects_unauthorized_roles_and_other_users(self):
        with self.assertRaises(rbac.RBACError):
            rbac.create_session(request_for(self.bob), self.bob_m, [role(OWNER)])
        with self.assertRaises(rbac.RBACError):
            rbac.create_session(request_for(self.bob), self.acme)

    def test_drop_and_add_active_role(self):
        request = request_for(self.alice)
        rbac.create_session(request, self.acme)
        rbac.drop_active_role(request, role(OWNER))
        self.assertFalse(
            rbac.check_access(request, "orgs.delete_organization", self.org)
        )
        self.assertTrue(rbac.check_access(request, "orgs.invite_member", self.org))
        with self.assertRaises(rbac.RBACError):
            rbac.drop_active_role(request, role(OWNER))
        rbac.add_active_role(request, role(OWNER))
        self.assertTrue(
            rbac.check_access(request, "orgs.delete_organization", self.org)
        )
        with self.assertRaises(rbac.RBACError):
            rbac.add_active_role(request, role(OWNER))

    def test_add_active_role_requires_authorization(self):
        request = request_for(self.bob)
        rbac.create_session(request, self.bob_m)
        with self.assertRaises(rbac.RBACError):
            rbac.add_active_role(request, role(ADMIN))

    def test_session_tracks_assignments_across_requests(self):
        session = SessionStore()
        rbac.create_session(request_for(self.bob, session), self.bob_m)
        # AssignUser during a session: the new role is active on the next request.
        rbac.assign_user(self.bob_m, role(ADMIN))
        self.assertTrue(
            rbac.check_access(
                request_for(self.bob, session), "orgs.invite_member", self.org
            )
        )
        # Admin inherits member, so member stays active while admin is held.
        rbac.deassign_user(self.bob_m, role(MEMBER))
        names = {r.name for r in rbac.session_roles(request_for(self.bob, session))}
        self.assertEqual(names, {ADMIN, MEMBER})
        # DeassignUser during a session: the role is inactive on the next request.
        rbac.assign_user(self.bob_m, role(MEMBER))
        rbac.deassign_user(self.bob_m, role(ADMIN))
        later = request_for(self.bob, session)
        self.assertEqual([r.name for r in rbac.session_roles(later)], [MEMBER])
        self.assertFalse(rbac.check_access(later, "orgs.invite_member", self.org))

    def test_dropped_role_stays_dropped_across_requests(self):
        session = SessionStore()
        rbac.create_session(request_for(self.alice, session), self.acme)
        rbac.drop_active_role(request_for(self.alice, session), role(OWNER))
        later = request_for(self.alice, session)
        self.assertNotIn(OWNER, {r.name for r in rbac.session_roles(later)})
        self.assertFalse(rbac.check_access(later, "orgs.delete_organization", self.org))

    def test_check_access_scopes_object_type_and_organization(self):
        request = request_for(self.alice)
        rbac.create_session(request, self.acme)
        other = Organization.create_with_owner("Globex", self.bob).organization
        self.assertFalse(rbac.check_access(request, "orgs.view_organization", other))
        self.assertFalse(
            rbac.check_access(request, "orgs.view_organization", role(OWNER))
        )
        self.assertFalse(rbac.check_access(request, "orgs.no_such_op", self.org))

    def test_no_session_without_membership_or_login(self):
        loner = User.objects.create_user(email="lone@example.com", username="lone")
        self.assertIsNone(rbac.current_session(request_for(loner)))
        self.assertIsNone(rbac.current_session(request_for(None)))
        self.assertFalse(
            rbac.check_access(request_for(loner), "orgs.view_organization", self.org)
        )

    def test_delete_session(self):
        request = request_for(self.alice)
        rbac.create_session(request, self.acme)
        rbac.delete_session(request)
        self.assertNotIn(rbac.SESSION_KEY, request.session)


class ReviewFunctionTests(RBACTestCase):
    """§6.1.3 / §6.1.4 / §6.2.1.3 / §6.2.1.4"""

    def test_assigned_versus_authorized(self):
        self.assertEqual(list(rbac.assigned_users(role(MEMBER), self.org)), [self.bob])
        self.assertEqual(
            set(rbac.authorized_users(role(MEMBER), self.org)), {self.alice, self.bob}
        )
        self.assertEqual([r.name for r in rbac.assigned_roles(self.acme)], [OWNER])
        self.assertEqual(
            {r.name for r in rbac.authorized_roles(self.acme)}, {OWNER, ADMIN, MEMBER}
        )

    def test_permission_review(self):
        self.assertEqual(rbac.user_permissions(self.bob_m), {"orgs.view_organization"})
        self.assertEqual(
            rbac.role_operations_on_object(role(ADMIN), self.org),
            {"view_organization", "invite_member", "manage_members"},
        )
        self.assertIn(
            "delete_organization", rbac.user_operations_on_object(self.acme, self.org)
        )
        other = Organization.create_with_owner("Globex", self.bob).organization
        self.assertEqual(rbac.user_operations_on_object(self.acme, other), set())

    def test_session_review(self):
        request = request_for(self.bob)
        rbac.create_session(request, self.bob_m)
        self.assertEqual([r.name for r in rbac.session_roles(request)], [MEMBER])
        self.assertEqual(rbac.session_permissions(request), {"orgs.view_organization"})
