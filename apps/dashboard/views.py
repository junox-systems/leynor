from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

from apps.orgs.rbac import current_session
from apps.projects.models import Project

from .panels import activity_payload

RECENT = 5


class DashboardView(LoginRequiredMixin, TemplateView):
    """The organization at a glance: projects, their campaigns, their outputs."""

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = current_session(self.request)
        if session is None:
            context.update(rows=[], awaiting=[], total=0)
            return context

        projects = list(
            Project.objects.filter(
                organization=session.organization,
                status=Project.Status.ACTIVE,
            ).prefetch_related("campaigns")
        )
        rows = [
            {
                "project": project,
                "campaigns": [
                    {"campaign": campaign, "units": campaign.units()}
                    for campaign in project.campaigns.all()
                ],
            }
            for project in projects
        ]
        awaiting = [
            {
                "project": row["project"],
                "campaign": entry["campaign"],
                "unit": unit["unit"],
                "url": unit["url"],
            }
            for row in rows
            for entry in row["campaigns"]
            for unit in entry["units"]
            if getattr(unit["unit"], "needs_person", False)
        ]
        context.update(rows=rows[:RECENT], awaiting=awaiting, total=len(projects))
        return context


class ActivityView(LoginRequiredMixin, TemplateView):
    """Recent audited changes, with a live refresh through the DMR endpoint."""

    template_name = "dashboard/activity.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payload"] = {
            "activity": activity_payload(self.request.user),
            # Resolved server-side so no island ever hardcodes a URL.
            "urls": {"activity": reverse("dashboard-activity")},
        }
        return context
