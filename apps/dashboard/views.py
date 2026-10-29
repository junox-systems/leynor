# apps/dashboard/views.py

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

from apps.orgs.rbac import current_session

from .panels import account_payload, activity_payload, org_payload


class DashboardView(LoginRequiredMixin, TemplateView):
    """Authenticated home. Panels are Svelte children of one Dashboard root."""

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # One payload dict -> one json_script node -> props of the Svelte root.
        context["payload"] = {
            "account": account_payload(user),
            "org": org_payload(current_session(self.request)),
        }
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
