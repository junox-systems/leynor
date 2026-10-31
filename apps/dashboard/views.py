from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

from apps.campaigns.models import Campaign
from apps.orgs.rbac import current_session

from .panels import activity_payload

RECENT = 5


class DashboardView(LoginRequiredMixin, TemplateView):
    """Today: the campaigns in play, and what waits on a person."""

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = current_session(self.request)
        if session is None:
            context.update(rows=[], awaiting=[], total=0)
            return context

        campaigns = list(
            Campaign.objects.filter(
                project__organization=session.organization
            ).select_related("project")
        )
        rows = [
            {"campaign": campaign, "units": campaign.units()} for campaign in campaigns
        ]
        awaiting = [
            {"campaign": row["campaign"], "unit": unit["unit"], "url": unit["url"]}
            for row in rows
            for unit in row["units"]
            if getattr(unit["unit"], "needs_person", False)
        ]
        context.update(rows=rows[:RECENT], awaiting=awaiting, total=len(campaigns))
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
