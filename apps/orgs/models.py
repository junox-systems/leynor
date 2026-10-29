# apps/orgs/models.py
"""Teams with role-based access control.

Users belong to organizations through Membership; attach billing, quotas and
shared data to Organization, not User.

Access control follows ANSI INCITS 359-2004 (Core RBAC + Limited Role
Hierarchies). Its data elements (§5.1, §5.2) map onto these models:

    USERS     User
    ROLES     Role
    OPS       Permission.codename         e.g. "invite_member"
    OBS       Permission.content_type     e.g. Organization; instances are
                                          scoped to one organization
    PRMS      Permission                  (operation, object type)
    PA        Role.permissions
    UA        Membership.roles            assignments are per organization
    RH        Role.descendant             one immediate descendant per role
    SESSIONS  the Django session          see apps/orgs/rbac.py

The functional specification (AddRole, AssignUser, CheckAccess, ...) lives in
apps/orgs/rbac.py. Change roles and assignments through those functions so
the validity rules of the standard hold.
"""

import secrets
from datetime import timedelta

from auditlog.registry import auditlog
from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import BaseModel

# Built-in role names. apps.orgs.rbac.seed_default_roles creates the rows.
# Code relies on OWNER (every organization keeps one) and MEMBER (invitees).
OWNER, ADMIN, MEMBER = "owner", "admin", "member"

NEEDS_OWNER = (
    "An organization needs an owner. Promote someone else first, or delete it."
)

# Invitations send email from your domain; cap them so one account cannot
# turn the app into a mail cannon (and get the sender suspended).
MAX_PENDING_INVITATIONS = 50


class Organization(BaseModel):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Membership", related_name="organizations"
    )

    class Meta(BaseModel.Meta):
        # OPS on the Organization object type, next to Django's built-in
        # view/change/delete_organization. Granted to roles, never to users.
        permissions = [
            ("invite_member", "Can invite people to the organization"),
            ("manage_members", "Can assign roles to and remove members"),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def create_with_owner(cls, name, user):
        """New organization with `user` as its first member, assigned the owner role."""
        with transaction.atomic():
            org = cls.objects.create(name=name)
            membership = Membership.objects.create(organization=org, user=user)
            membership.roles.add(Role.objects.get(name=OWNER))
        return membership

    def owners(self):
        return self.memberships.filter(roles__name=OWNER)

    def lock(self):
        """Row-lock this organization until the surrounding transaction ends.

        Serializes changes that must keep an owner, so two owners demoting each
        other at the same moment cannot leave the organization with none.
        """
        Organization.objects.select_for_update().filter(pk=self.pk).first()

    def ensure_owner_remains(self, losing):
        """Raise if `losing`, a Membership about to lose the owner role, is the last owner.

        Call inside a transaction, after lock().
        """
        if not self.owners().exclude(pk=losing.pk).exists():
            raise ValidationError(NEEDS_OWNER)

    def has_member_email(self, email):
        """True if a member owns `email`: their login address or any verified one."""
        return (
            self.members.filter(email__iexact=email).exists()
            or self.members.filter(
                emailaddress__email__iexact=email, emailaddress__verified=True
            ).exists()
        )

    def invite(self, email, invited_by):
        """Create a fresh invitation for `email`; the caller emails the link.

        Re-inviting replaces the old invite: fresh token, fresh expiry.
        Raises ValidationError for existing members and at the pending cap.
        """
        if self.has_member_email(email):
            raise ValidationError("Already a member.")
        if self.invitations.exclude(email=email).count() >= MAX_PENDING_INVITATIONS:
            raise ValidationError(
                f"At most {MAX_PENDING_INVITATIONS} pending invitations. "
                "Revoke some first."
            )
        with transaction.atomic():
            self.invitations.filter(email=email).delete()
            return Invitation.objects.create(
                organization=self, email=email, invited_by=invited_by
            )


class Role(BaseModel):
    """An RBAC role (ANSI INCITS 359-2004 §5.1): a named job function.

    Roles are global; users get them per organization through Membership.roles.
    `descendant` builds a limited role hierarchy (§5.2): this role inherits
    every permission of its descendant, and each role has at most one immediate
    descendant. Several roles may share the same descendant.
    """

    name = models.SlugField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True)
    permissions = models.ManyToManyField(
        Permission, blank=True, related_name="org_roles"
    )
    descendant = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ascendants",
        help_text="Immediate junior role whose permissions this role inherits.",
    )

    class Meta(BaseModel.Meta):
        ordering = ["name"]

    def __str__(self):
        return self.name

    def juniors(self):
        """This role and every role it inherits, senior first: {r | self ≥ r}."""
        chain, role = [], self
        while role is not None and role not in chain:
            chain.append(role)
            role = role.descendant
        return chain

    def clean(self):
        # AddInheritance validity (§6.2.2.1): r_desc must not already inherit
        # r_asc, or the hierarchy would contain a cycle.
        if self.pk and self.descendant_id:
            if any(r.pk == self.pk for r in self.descendant.juniors()):
                raise ValidationError(
                    {"descendant": "That role already inherits this one (cycle)."}
                )


class Membership(BaseModel):
    """A user's place in an organization. `roles` is the UA relation for that org."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="memberships")

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="unique_org_member"
            )
        ]

    def __str__(self):
        return f"{self.user} in {self.organization}"

    @property
    def is_owner(self):
        # .all() so a prefetch_related("roles") is reused.
        return any(role.name == OWNER for role in self.roles.all())

    def remove(self):
        """Leave, or be removed. Every role assignment goes with the membership."""
        with transaction.atomic():
            self.organization.lock()
            if self.is_owner:
                self.organization.ensure_owner_remains(self)
            self.delete()


INVITATION_TTL = timedelta(days=7)


def invitation_token():
    return secrets.token_urlsafe(32)


class Invitation(BaseModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, default=invitation_token)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"], name="unique_org_invitation"
            )
        ]

    def __str__(self):
        return f"{self.email} to {self.organization}"

    @property
    def is_expired(self):
        return timezone.now() - self.created_at > INVITATION_TTL


auditlog.register(Organization)
auditlog.register(Role, m2m_fields={"permissions"})
# m2m_fields: every AssignUser / DeassignUser lands in the audit log.
auditlog.register(Membership, m2m_fields={"roles"})
auditlog.register(Invitation, exclude_fields=["token"])


def release_user(user):
    """Run before deleting a user (DeleteUser) so no organization is left empty or ownerless.

    Orgs where they are the only member are deleted; orgs left without an
    owner hand ownership to the longest-standing remaining member.
    """
    owner = Role.objects.get(name=OWNER)
    for membership in user.memberships.select_related("organization"):
        org = membership.organization
        with transaction.atomic():
            org.lock()
            others = org.memberships.exclude(user=user)
            if not others.exists():
                org.delete()
            elif membership.is_owner and not org.owners().exclude(user=user).exists():
                others.order_by("created_at").first().roles.add(owner)
