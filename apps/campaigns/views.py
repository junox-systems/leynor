"""Campaign pages. Every view is scoped to the session's organization."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.campaigns.forms import CampaignForm
from apps.campaigns.models import Campaign
from apps.orgs.rbac import current_session
from apps.projects.models import Project


def _organization(request):
    session = current_session(request)
    return session.organization if session else None


def _campaign(request, pk):
    org = _organization(request)
    if org is None:
        raise Http404("No organization.")
    # Scoped by organization: another tenant's campaign is a 404, not a 403.
    return get_object_or_404(
        Campaign.objects.select_related("project", "audience"),
        pk=pk,
        project__organization=org,
    )


@login_required
def campaign_list(request):
    org = _organization(request)
    campaigns = (
        Campaign.objects.filter(
            project__organization=org, project__status=Project.Status.ACTIVE
        ).select_related("project", "audience")
        if org
        else Campaign.objects.none()
    )
    return render(request, "campaigns/list.html", {"campaigns": campaigns})


@login_required
def campaign_detail(request, pk):
    campaign = _campaign(request, pk)
    return render(
        request,
        "campaigns/detail.html",
        {"campaign": campaign, "units": campaign.units()},
    )


@login_required
@require_http_methods(["GET", "POST"])
def campaign_new(request, project_pk):
    org = _organization(request)
    if org is None:
        messages.info(request, "A campaign belongs to an organization. Create one first.")
        return redirect("orgs")
    project = get_object_or_404(Project, pk=project_pk, organization=org)
    form = CampaignForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        campaign = form.save()
        messages.success(request, f"{campaign.title} briefed.")
        return redirect("campaign_detail", pk=campaign.pk)
    return render(
        request, "campaigns/new.html", {"form": form, "project": project}
    )
