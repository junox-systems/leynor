# apps/dashboard/views.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

from apps.orgs.rbac import current_session

from .panels import activity_payload


class DashboardView(LoginRequiredMixin, TemplateView):
    """Today: what waits on a person, and the reels moving down the route."""

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = current_session(self.request)
        projects = (
            list(session.organization.projects.prefetch_related("gates"))
            if session
            else []
        )
        context["awaiting"] = [project for project in projects if project.needs_person]
        context["projects"] = projects[:5]
        context["total"] = len(projects)
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
