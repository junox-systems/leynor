"""Reel pages and their gate decisions. Every view is org-scoped."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.campaigns.models import Campaign
from apps.instagram.forms import ReelForm
from apps.instagram.gates import GateResult
from apps.instagram.models import GateOutOfOrder, Reel
from apps.orgs.rbac import current_session
from apps.projects.models import Project


def _organization(request):
    session = current_session(request)
    return session.organization if session else None


def _campaign(request, pk):
    org = _organization(request)
    if org is None:
        raise Http404("No organization.")
    return get_object_or_404(
        Campaign.objects.select_related("project"), pk=pk, project__organization=org
    )


def _reel(request, pk):
    org = _organization(request)
    if org is None:
        raise Http404("No organization.")
    # Scoped by organization: another tenant's reel is a 404, not a 403.
    return get_object_or_404(
        Reel.objects.select_related("campaign__project").prefetch_related("gates"),
        pk=pk,
        campaign__project__organization=org,
    )


@login_required
def reel_list(request):
    org = _organization(request)
    reels = (
        Reel.objects.filter(
            campaign__project__organization=org,
            campaign__project__status=Project.Status.ACTIVE,
        )
        .select_related("campaign__project")
        .prefetch_related("gates")
        if org
        else Reel.objects.none()
    )
    return render(request, "instagram/list.html", {"reels": reels})


@login_required
@require_http_methods(["GET", "POST"])
def reel_new(request, campaign_pk):
    campaign = _campaign(request, campaign_pk)
    form = ReelForm(request.POST or None, campaign=campaign)
    if request.method == "POST" and form.is_valid():
        reel = Reel.create(campaign=campaign, **form.cleaned_data)
        messages.success(request, f"{reel.title} created on Spark.")
        return redirect("reel_detail", pk=reel.pk)
    return render(
        request, "instagram/new.html", {"form": form, "campaign": campaign}
    )


@login_required
def reel_detail(request, pk):
    reel = _reel(request, pk)
    return render(
        request, "instagram/detail.html", {"reel": reel, "route": reel.route()}
    )


@login_required
@require_POST
def gate_decide(request, pk, step):
    reel = _reel(request, pk)
    gate = get_object_or_404(reel.gates, step=step)
    name = gate.get_step_display()
    action = request.POST.get("action")
    note = request.POST.get("note", "")
    try:
        if action == "approve":
            result = GateResult.APPROVED if gate.kind == "human" else GateResult.AUTO
            gate.decide(result, request.user, note)
            messages.success(request, f"{name} passed.")
        elif action == "reject":
            if gate.kind != "human":
                raise ValidationError(
                    f"{name} passes on evidence; only a person can send a step back."
                )
            gate.decide(GateResult.REJECTED, request.user, note)
            messages.warning(request, f"{name} sent back.")
        elif action == "reopen":
            gate.reopen()
            messages.info(request, f"{name} is back in play.")
        else:
            raise ValidationError("Unknown action.")
    except (GateOutOfOrder, ValidationError) as exc:
        detail = getattr(exc, "messages", None)
        messages.error(request, " ".join(detail) if detail else str(exc))
    return redirect("reel_detail", pk=reel.pk)


@login_required
@require_POST
def reel_delete(request, pk):
    reel = _reel(request, pk)
    title = reel.title
    campaign_pk = reel.campaign_id
    reel.delete()
    messages.success(request, f"{title} deleted.")
    return redirect("campaign_detail", pk=campaign_pk)
