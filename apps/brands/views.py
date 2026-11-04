"""Brand pages. Every view is scoped to the session's organization."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.brands.forms import AudienceForm, BrandForm
from apps.brands.models import Brand
from apps.orgs.rbac import current_session


def _organization(request):
    session = current_session(request)
    return session.organization if session else None


def _brand(request, pk):
    org = _organization(request)
    if org is None:
        raise Http404("No organization.")
    return get_object_or_404(Brand, pk=pk, organization=org)


@login_required
def brand_list(request):
    org = _organization(request)
    brands = (
        org.brands.prefetch_related("projects", "audiences")
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


@login_required
@require_http_methods(["GET", "POST"])
def brand_detail(request, pk):
    """One brand and the audiences it speaks to. The add form posts here."""
    brand = _brand(request, pk)
    form = AudienceForm(request.POST or None, brand=brand)
    if request.method == "POST" and form.is_valid():
        audience = form.save()
        messages.success(request, f"{audience.name} added to {brand.name}.")
        return redirect("brand_detail", pk=brand.pk)
    return render(
        request,
        "brands/detail.html",
        {"brand": brand, "audiences": brand.audiences.all(), "form": form},
    )
