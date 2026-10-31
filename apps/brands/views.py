"""Brand pages. Every view is scoped to the session's organization."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.brands.forms import BrandForm
from apps.brands.models import Brand
from apps.orgs.rbac import current_session


def _organization(request):
    session = current_session(request)
    return session.organization if session else None


@login_required
def brand_list(request):
    org = _organization(request)
    brands = (
        org.brands.prefetch_related("projects")
        if org
        else Brand.objects.none()
    )
    return render(request, "brands/list.html", {"brands": brands})


@login_required
@require_http_methods(["GET", "POST"])
def brand_new(request):
    org = _organization(request)
    if org is None:
        messages.info(request, "A brand belongs to an organization. Create one first.")
        return redirect("orgs")
    form = BrandForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        brand = form.save()
        messages.success(request, f"{brand.name} added.")
        return redirect("brands")
    return render(request, "brands/new.html", {"form": form})
