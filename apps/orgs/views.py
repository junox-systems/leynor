import uuid

from allauth.account.decorators import reauthentication_required
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from django_q.tasks import async_task

from . import rbac
from .forms import InviteForm, OrganizationForm
from .models import MEMBER, Invitation, Membership, Organization, Role


def _membership(request, pk):
    """The requester's membership in org `pk`, made the RBAC session's org.

    404 for non-members so org ids don't leak. Opening an organization's
    pages switches the session to it, so the app bar matches the page.
    """
    membership = get_object_or_404(
        Membership.objects.select_related("organization"),
        organization_id=pk,
        user=request.user,
    )
    rbac.activate(request, membership)
    return membership


def _require(request, pk, perm):
    """_membership, then CheckAccess(perm) on the organization or 403."""
    membership = _membership(request, pk)
    if not rbac.check_access(request, perm, membership.organization):
        raise PermissionDenied
    return membership


def _error(request, exc):
    messages.error(request, " ".join(exc.messages))


def _uuid(value):
    """Parse a posted id; None when malformed, so lookups 404 instead of 500."""
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


@login_required
@require_http_methods(["GET", "POST"])
def org_list(request):
    form = OrganizationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        membership = Organization.create_with_owner(
            form.cleaned_data["name"], request.user
        )
        return redirect("org_detail", pk=membership.organization_id)
    memberships = request.user.memberships.select_related(
        "organization"
    ).prefetch_related("roles")
    return render(request, "orgs/list.html", {"memberships": memberships, "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def org_detail(request, pk):
    membership = _require(request, pk, "orgs.view_organization")
    org = membership.organization
    can_invite = rbac.check_access(request, "orgs.invite_member", org)
    form = InviteForm(request.POST or None)
    if request.method == "POST":
        if not can_invite:
            raise PermissionDenied
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                invitation = org.invite(email, invited_by=request.user)
            except ValidationError as exc:
                form.add_error("email", exc)
            else:
                accept_url = request.build_absolute_uri(
                    reverse("invitation_accept", args=[invitation.token])
                )
                async_task(
                    "apps.orgs.tasks.send_invitation_email", invitation.id, accept_url
                )
                messages.success(request, f"Invitation sent to {email}.")
                return redirect("org_detail", pk=pk)
    memberships = list(org.memberships.select_related("user").prefetch_related("roles"))
    manageable = rbac.manageable_members(request, memberships)
    return render(
        request,
        "orgs/detail.html",
        {
            "org": org,
            "membership": membership,
            "members": [
                {"m": m, "manageable": m.pk in manageable} for m in memberships
            ],
            "assignable_roles": rbac.administrable_roles(request),
            "invitations": org.invitations.all() if can_invite else [],
            "can_invite": can_invite,
            "can_delete": rbac.check_access(request, "orgs.delete_organization", org),
            "form": form,
        },
    )


@login_required
@require_POST
def org_delete(request, pk):
    # Authorize first: members get 403, not a pointless password prompt.
    return _delete_org(request, _require(request, pk, "orgs.delete_organization"))


@reauthentication_required
def _delete_org(request, membership):
    membership.organization.delete()
    messages.success(request, "Organization deleted.")
    return redirect("orgs")


@login_required
@require_POST
def membership_remove(request, pk, membership_pk):
    """Managers remove members who hold no more than they do; anyone can leave."""
    me = _membership(request, pk)
    target = get_object_or_404(
        Membership.objects.select_related("organization"),
        pk=membership_pk,
        organization_id=pk,
    )
    if target != me and not rbac.can_manage_member(request, target):
        raise PermissionDenied
    try:
        target.remove()
    except ValidationError as exc:
        _error(request, exc)
        return redirect("org_detail", pk=pk)
    if target == me:
        rbac.delete_session(request)
        return redirect("orgs")
    return redirect("org_detail", pk=pk)


@login_required
@require_POST
def membership_role(request, pk, membership_pk):
    """Toggle one role on a member: AssignUser if unassigned, else DeassignUser."""
    _membership(request, pk)
    target = get_object_or_404(
        Membership.objects.select_related("organization"),
        pk=membership_pk,
        organization_id=pk,
    )
    role_id = _uuid(request.POST.get("role"))
    role = Role.objects.filter(pk=role_id).first() if role_id else None
    if role is None:
        return redirect("org_detail", pk=pk)
    if not (
        rbac.can_manage_member(request, target)
        and rbac.can_administer_role(request, role)
    ):
        raise PermissionDenied
    try:
        if target.roles.filter(pk=role.pk).exists():
            rbac.deassign_user(target, role)
        else:
            rbac.assign_user(target, role)
    except ValidationError as exc:
        _error(request, exc)
    return redirect("org_detail", pk=pk)


@login_required
@require_POST
def invitation_revoke(request, pk, invitation_pk):
    _require(request, pk, "orgs.invite_member")
    get_object_or_404(Invitation, pk=invitation_pk, organization_id=pk).delete()
    return redirect("org_detail", pk=pk)


@login_required
@require_http_methods(["GET", "POST"])
def invitation_accept(request, token):
    invitation = get_object_or_404(
        Invitation.objects.select_related("organization"), token=token
    )
    # The token alone is not enough: it was emailed, so require the account
    # to own that address (verified) before joining.
    email_matches = request.user.emailaddress_set.filter(
        email__iexact=invitation.email, verified=True
    ).exists()
    if invitation.is_expired:
        return render(
            request, "orgs/accept.html", {"invitation": invitation}, status=410
        )
    if request.method == "POST" and email_matches:
        with transaction.atomic():
            membership, created = Membership.objects.get_or_create(
                organization=invitation.organization, user=request.user
            )
            if created:
                rbac.assign_user(membership, Role.objects.get(name=MEMBER))
            invitation.delete()
        rbac.create_session(request, membership)
        return redirect("org_detail", pk=invitation.organization_id)
    return render(
        request,
        "orgs/accept.html",
        {"invitation": invitation, "email_matches": email_matches},
        status=200 if email_matches else 403,
    )


@login_required
@require_POST
def org_switch(request):
    """Switch the RBAC session to another of the user's organizations."""
    membership = get_object_or_404(
        Membership,
        organization_id=_uuid(request.POST.get("organization")),
        user=request.user,
    )
    rbac.create_session(request, membership)
    messages.success(request, f"Switched to {membership.organization.name}.")
    return redirect("dashboard")
