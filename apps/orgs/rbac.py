# apps/orgs/rbac.py
"""Role-based access control, after ANSI INCITS 359-2004.

Standard: ANSI INCITS 359-2004, "American National Standard for Information
Technology – Role Based Access Control" (superseded by INCITS 359-2012 (R2022);
the parts used here are unchanged in substance). Components implemented:

    Core RBAC                 §5.1 model, §6.1 functional specification
    Limited Role Hierarchies  §5.2 model, §6.2.2 functional specification

Not implemented (optional per §2 Conformance): general role hierarchies,
static and dynamic separation of duty (§5.3, §6.3, §6.4).

How the standard's elements map onto Django lives in apps/orgs/models.py.
Each public function below names the standard function it implements. Where
the standard leaves a choice to the implementation, the docstring records it.

Two deliberate extensions, both outside the standard:

* Tenancy. UA is scoped per organization (Membership.roles) and an RBAC
  session is bound to one membership. CheckAccess only grants access to
  objects of the session's organization.
* Delegated administration. Organization members run the administrative
  commands on their own org, guarded by `can_administer_role` and
  `can_manage_member` (no one can grant or remove more than they hold).

Sessions: the RBAC session rides in the Django session under SESSION_KEY as
{"membership": <id>, "dropped": [<role id>, ...]}. Active roles are the
user's authorized roles minus the ones they dropped, so session_roles is
always a subset of the authorized roles (§6.2.1.2). Implementation
decision: a role assigned during a session becomes active at once, and a
deassigned or deleted role stops being active at once. Logging out flushes
the Django session, which is DeleteSession.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from django.apps import apps as global_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ADMIN, MEMBER, OWNER, Membership, Organization, Role

SESSION_KEY = "rbac"


class RBACError(ValidationError):
    """A command or function was called outside its validity conditions."""


# ---------------------------------------------------------------------------
# Hierarchy helpers
# ---------------------------------------------------------------------------


def _descendants_by_id():
    """{role id: immediate descendant id} for every role. Roles are few."""
    return dict(Role.objects.values_list("id", "descendant_id"))


def _juniors(role_ids, links=None):
    """Ids of the given roles and every role they inherit: {r | q ≥ r, q ∈ role_ids}."""
    links = _descendants_by_id() if links is None else links
    found = set()
    for role_id in role_ids:
        while role_id is not None and role_id not in found:
            found.add(role_id)
            role_id = links.get(role_id)
    return found


def _seniors(role, links=None):
    """Ids of `role` and every role that inherits it: {q | q ≥ role}."""
    links = _descendants_by_id() if links is None else links
    return {q for q in links if role.pk in _juniors([q], links)}


def _permissions_of(role_ids):
    """{"app_label.codename": model name} directly assigned (PA) to the given roles."""
    rows = (
        Permission.objects.filter(org_roles__in=role_ids)
        .values_list("content_type__app_label", "codename", "content_type__model")
        .distinct()
    )
    return {f"{app}.{codename}": model for app, codename, model in rows}


def _permission(perm):
    """Accept a Permission or an "app_label.codename" string."""
    if isinstance(perm, Permission):
        return perm
    app_label, _, codename = perm.partition(".")
    try:
        return Permission.objects.get(
            content_type__app_label=app_label, codename=codename
        )
    except Permission.DoesNotExist:
        raise RBACError(f"No such permission: {perm}") from None


def _organization_of(obj):
    """The organization an RBAC-protected object belongs to, or None."""
    if isinstance(obj, Organization):
        return obj
    return getattr(obj, "organization", None)


# ---------------------------------------------------------------------------
# §6.1.1 Administrative commands for Core RBAC
#
# AddUser / DeleteUser: users are created by allauth signup and deleted by
# apps.users.views.delete_account, which calls models.release_user first and
# logs the user out (terminating their sessions). Deleting the User cascades
# to Membership, which removes the user's UA entries.
# ---------------------------------------------------------------------------


def add_role(name, description=""):
    """AddRole. Valid iff no role named `name` exists. The new role has no users or permissions."""
    if Role.objects.filter(name=name).exists():
        raise RBACError(f"Role {name!r} already exists.")
    return Role.objects.create(name=name, description=description)


def delete_role(role):
    """DeleteRole. Removes the role with its UA and PA entries.

    Sessions: the role is dropped from any session where it is active, which
    stays open (see current_session). The owner role cannot be deleted: every
    organization must keep an owner.
    """
    if role.name == OWNER:
        raise RBACError("The owner role cannot be deleted.")
    role.delete()


def assign_user(membership, role):
    """AssignUser. Valid iff the user is not already assigned to `role` in this organization."""
    if membership.roles.filter(pk=role.pk).exists():
        raise RBACError(f"Already assigned to {role}.")
    membership.roles.add(role)


def deassign_user(membership, role):
    """DeassignUser. Valid iff the user is assigned to `role` in this organization.

    Sessions: the role stops being active on the user's next request.
    Organization invariants (application policy, checked under the org lock):
    the last owner keeps the owner role, and a member keeps at least one role
    (remove the member instead).
    """
    with transaction.atomic():
        membership.organization.lock()
        assigned = set(membership.roles.values_list("pk", flat=True))
        if role.pk not in assigned:
            raise RBACError(f"Not assigned to {role}.")
        if role.name == OWNER:
            membership.organization.ensure_owner_remains(membership)
        if assigned == {role.pk}:
            raise RBACError("A member needs at least one role. Remove them instead.")
        membership.roles.remove(role)


def grant_permission(role, perm):
    """GrantPermission. `perm` is a Permission or "app_label.codename" (an (operation, object type) pair)."""
    role.permissions.add(_permission(perm))


def revoke_permission(role, perm):
    """RevokePermission. Valid iff the permission is assigned to `role`."""
    perm = _permission(perm)
    if not role.permissions.filter(pk=perm.pk).exists():
        raise RBACError(f"{role} does not hold {perm}.")
    role.permissions.remove(perm)


# ---------------------------------------------------------------------------
# §6.2.1.1 / §6.2.2.1 Administrative commands for Limited Role Hierarchies
# ---------------------------------------------------------------------------


def add_inheritance(r_asc, r_desc):
    """AddInheritance (limited, §6.2.2.1): r_asc becomes an immediate ascendant of r_desc.

    Valid iff r_asc has no descendant yet and r_desc does not inherit r_asc
    (which also rules out r_asc == r_desc), so the hierarchy stays acyclic.
    """
    if r_asc.descendant_id is not None:
        raise RBACError(f"{r_asc} already inherits {r_asc.descendant}.")
    if r_asc.pk in _juniors([r_desc.pk]):
        raise RBACError(f"{r_desc} already inherits {r_asc} (cycle).")
    r_asc.descendant = r_desc
    r_asc.save(update_fields=["descendant", "updated_at"])


def delete_inheritance(r_asc, r_desc):
    """DeleteInheritance. Valid iff r_asc is an immediate ascendant of r_desc.

    The inheritance relation is computed from the immediate links on every
    call, so it is always the reflexive-transitive closure the standard asks for.
    """
    if r_asc.descendant_id != r_desc.pk:
        raise RBACError(f"{r_asc} does not immediately inherit {r_desc}.")
    r_asc.descendant = None
    r_asc.save(update_fields=["descendant", "updated_at"])


def add_ascendant(name, r_desc, description=""):
    """AddAscendant: AddRole(name) + AddInheritance(name, r_desc)."""
    with transaction.atomic():
        role = add_role(name, description)
        add_inheritance(role, r_desc)
    return role


def add_descendant(r_asc, name, description=""):
    """AddDescendant: AddRole(name) + AddInheritance(r_asc, name)."""
    with transaction.atomic():
        role = add_role(name, description)
        add_inheritance(r_asc, role)
    return role


# ---------------------------------------------------------------------------
# §6.1.2 / §6.2.1.2 Supporting system functions
# ---------------------------------------------------------------------------


@dataclass
class Session:
    """One RBAC session: a user, through one membership, with a set of active roles."""

    membership: Membership
    roles: list = field(default_factory=list)
    # {"app_label.codename": model name} available through the active roles.
    permissions: dict = field(default_factory=dict)

    @property
    def organization(self):
        return self.membership.organization


def _store(request, membership, dropped=()):
    """Save the session (only on change) and build it for this request."""
    authorized = {r.pk for r in authorized_roles(membership)}
    dropped = {pk for pk in map(_as_uuid, dropped) if pk in authorized}
    data = {"membership": str(membership.pk), "dropped": sorted(map(str, dropped))}
    # Assign only on change: every assignment marks the Django session dirty.
    if request.session.get(SESSION_KEY) != data:
        request.session[SESSION_KEY] = data
    active = authorized - dropped
    roles = list(Role.objects.filter(pk__in=active))
    request._rbac_session = Session(membership, roles, _permissions_of(active))
    return request._rbac_session


def _as_uuid(value):
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def create_session(request, membership, active_roles=None):
    """CreateSession, with role hierarchies (§6.2.1.2).

    Valid iff the membership belongs to the requesting user and the active
    role set is a subset of the user's authorized roles in that organization.
    Default: every authorized role is active, so inherited permissions apply.
    A request holds one RBAC session; creating one replaces the previous.
    """
    if membership.user_id != request.user.pk:
        raise RBACError("A session can only be created for your own membership.")
    authorized = {r.pk for r in authorized_roles(membership)}
    wanted = authorized if active_roles is None else {r.pk for r in active_roles}
    if not wanted <= authorized:
        raise RBACError("Active roles must be authorized for the user.")
    return _store(request, membership, authorized - wanted)


def delete_session(request):
    """DeleteSession. Logging out also ends it, because logout flushes the Django session."""
    request.session.pop(SESSION_KEY, None)
    request._rbac_session = None


def current_session(request):
    """The request's RBAC session, created on first use; None for users without organizations.

    A session whose membership is gone (left, removed, org deleted) is
    replaced by one for the user's oldest remaining membership.
    """
    if hasattr(request, "_rbac_session"):
        return request._rbac_session
    request._rbac_session = None
    if not request.user.is_authenticated:
        return None
    data = request.session.get(SESSION_KEY) or {}
    memberships = request.user.memberships.select_related("organization")
    membership = None
    if data.get("membership"):
        membership = memberships.filter(pk=data["membership"]).first()
    if membership is None:
        membership = memberships.order_by("created_at").first()
        return create_session(request, membership) if membership else None
    return _store(request, membership, data.get("dropped", []))


def activate(request, membership):
    """Make `membership`'s organization the session's organization (CreateSession if it is not already)."""
    session = current_session(request)
    if session and session.membership.pk == membership.pk:
        return session
    return create_session(request, membership)


def _dropped(session):
    authorized = {r.pk for r in authorized_roles(session.membership)}
    return authorized - {r.pk for r in session.roles}


def add_active_role(request, role):
    """AddActiveRole. Valid iff the user is authorized for `role` and it is not active yet."""
    session = _require_session(request)
    if role.pk not in {r.pk for r in authorized_roles(session.membership)}:
        raise RBACError(f"Not authorized for {role}.")
    if role.pk in {r.pk for r in session.roles}:
        raise RBACError(f"{role} is already active.")
    return _store(request, session.membership, _dropped(session) - {role.pk})


def drop_active_role(request, role):
    """DropActiveRole. Valid iff `role` is active in the session."""
    session = _require_session(request)
    if role.pk not in {r.pk for r in session.roles}:
        raise RBACError(f"{role} is not active.")
    return _store(request, session.membership, _dropped(session) | {role.pk})


def check_access(request, perm, obj):
    """CheckAccess: may the session's subject perform operation `perm` on `obj`?

    `perm` is "app_label.codename". True iff some active role holds that
    permission, the permission's object type is `obj`'s type, and `obj`
    belongs to the session's organization.
    """
    session = current_session(request)
    org = _organization_of(obj)
    if session is None or org is None or org.pk != session.organization.pk:
        return False
    return perm.startswith(f"{obj._meta.app_label}.") and (
        session.permissions.get(perm) == obj._meta.model_name
    )


def _require_session(request):
    session = current_session(request)
    if session is None:
        raise RBACError("No active RBAC session.")
    return session


# ---------------------------------------------------------------------------
# §6.1.3 / §6.2.1.3 Review functions
# ---------------------------------------------------------------------------


def assigned_users(role, organization=None):
    """AssignedUsers: users assigned to `role`, in one organization or across all."""
    users = get_user_model().objects.filter(memberships__roles=role)
    if organization is not None:
        users = users.filter(memberships__organization=organization)
    return users.distinct()


def assigned_roles(membership):
    """AssignedRoles: roles assigned to the user in the membership's organization."""
    return membership.roles.all()


def authorized_users(role, organization=None):
    """AuthorizedUsers: users assigned to `role` or to any role that inherits it."""
    users = get_user_model().objects.filter(memberships__roles__in=_seniors(role))
    if organization is not None:
        users = users.filter(memberships__organization=organization)
    return users.distinct()


def authorized_roles(membership):
    """AuthorizedRoles: assigned roles plus every role they inherit."""
    assigned = membership.roles.values_list("id", flat=True)
    return Role.objects.filter(pk__in=_juniors(assigned))


# ---------------------------------------------------------------------------
# §6.1.4 / §6.2.1.4 Advanced review functions
# ---------------------------------------------------------------------------


def role_permissions(role):
    """RolePermissions (§6.2.1.4): permissions granted to or inherited by `role`, as "app_label.codename"."""
    return set(_permissions_of(_juniors([role.pk])))


def user_permissions(membership):
    """UserPermissions (§6.2.1.4): permissions through the user's authorized roles in that organization."""
    assigned = membership.roles.values_list("id", flat=True)
    return set(_permissions_of(_juniors(assigned)))


def session_roles(request):
    """SessionRoles: the session's active roles."""
    return list(_require_session(request).roles)


def session_permissions(request):
    """SessionPermissions: permissions of the session's active roles, as "app_label.codename"."""
    return set(_require_session(request).permissions)


def _operations(role_ids, obj):
    model = obj._meta.model_name
    app = obj._meta.app_label
    return {
        perm.partition(".")[2]
        for perm, perm_model in _permissions_of(role_ids).items()
        if perm_model == model and perm.startswith(f"{app}.")
    }


def role_operations_on_object(role, obj):
    """RoleOperationsOnObject (§6.2.1.4): operations `role` may perform on `obj`, inherited included."""
    return _operations(_juniors([role.pk]), obj)


def user_operations_on_object(membership, obj):
    """UserOperationsOnObject (§6.2.1.4): operations the user may perform on `obj`.

    Empty when `obj` belongs to another organization (tenancy extension).
    """
    org = _organization_of(obj)
    if org is None or org.pk != membership.organization_id:
        return set()
    assigned = membership.roles.values_list("id", flat=True)
    return _operations(_juniors(assigned), obj)


# ---------------------------------------------------------------------------
# Delegated administration (application policy, not part of INCITS 359)
# ---------------------------------------------------------------------------


def _role_permission_map():
    """{role id: every permission it holds, inherited included}. Two queries."""
    links = _descendants_by_id()
    direct = defaultdict(set)
    rows = Permission.objects.filter(org_roles__isnull=False).values_list(
        "org_roles", "content_type__app_label", "codename"
    )
    for role_id, app, codename in rows:
        direct[role_id].add(f"{app}.{codename}")
    return {
        role_id: set().union(*(direct[j] for j in _juniors([role_id], links)))
        for role_id in links
    }


def administrable_roles(request):
    """Roles the session's subject may assign or deassign (bulk can_administer_role)."""
    session = current_session(request)
    if session is None or not check_access(
        request, "orgs.manage_members", session.organization
    ):
        return []
    held, perms = set(session.permissions), _role_permission_map()
    return [r for r in Role.objects.all() if perms.get(r.pk, set()) <= held]


def manageable_members(request, memberships):
    """Ids of the memberships the subject may manage (bulk can_manage_member).

    Prefetch "roles" on `memberships` to keep this at three queries.
    """
    session = current_session(request)
    if session is None or not check_access(
        request, "orgs.manage_members", session.organization
    ):
        return set()
    held, perms = set(session.permissions), _role_permission_map()
    return {
        m.pk
        for m in memberships
        if m.organization_id == session.organization.pk
        and set().union(*(perms.get(r.pk, set()) for r in m.roles.all())) <= held
    }


def can_administer_role(request, role):
    """May the session's subject assign or deassign `role` in its organization?

    Needs orgs.manage_members, and every permission of `role` (inherited
    included) must already be the subject's: no one hands out more than they hold.
    """
    session = current_session(request)
    if session is None or not check_access(
        request, "orgs.manage_members", session.organization
    ):
        return False
    return role_permissions(role) <= set(session.permissions)


def can_manage_member(request, membership):
    """May the session's subject remove `membership` or change its roles?

    Needs orgs.manage_members in the target's organization, and the target
    may hold no permission the subject lacks (admins cannot remove owners).
    Includes the subject's own membership: stepping down cannot escalate.
    """
    session = current_session(request)
    if session is None or not check_access(
        request, "orgs.manage_members", membership.organization
    ):
        return False
    return user_permissions(membership) <= set(session.permissions)


# ---------------------------------------------------------------------------
# Default roles
# ---------------------------------------------------------------------------

# (name, description, descendant, permissions). Senior roles inherit the
# permissions of their descendant, so each lists only what it adds.
DEFAULT_ROLES = [
    (MEMBER, "Uses the organization.", None, ["orgs.view_organization"]),
    (
        ADMIN,
        "Invites people and manages members.",
        MEMBER,
        ["orgs.invite_member", "orgs.manage_members"],
    ),
    (
        OWNER,
        "Full control, including deleting the organization.",
        ADMIN,
        ["orgs.change_organization", "orgs.delete_organization"],
    ),
]


def seed_default_roles(sender, using="default", **kwargs):
    """post_migrate hook: create any missing default role with its default permissions.

    Idempotent and non-destructive: existing roles are never touched, so
    operator edits in the admin (permissions, hierarchy) survive every
    migrate. Fresh databases get their roles from migration orgs 0002; this
    covers test databases built without migrations and deleted defaults.
    """
    try:
        # Migrated to a state before the Role table (e.g. `migrate orgs 0001`).
        kwargs.get("apps", global_apps).get_model("orgs", "Role")
    except LookupError:
        return
    # apps.orgs precedes django.contrib.auth in INSTALLED_APPS, so this hook
    # runs before auth's; create this app's Permission rows first (idempotent).
    create_permissions(sender, verbosity=0, using=using)
    for name, description, descendant, perms in DEFAULT_ROLES:
        role, created = Role.objects.get_or_create(
            name=name, defaults={"description": description}
        )
        if not created:
            continue
        if descendant:
            role.descendant = Role.objects.filter(name=descendant).first()
            role.save(update_fields=["descendant", "updated_at"])
        role.permissions.add(*(_permission(p) for p in perms))
