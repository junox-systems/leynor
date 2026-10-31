"""Projects and the campaigns inside them. Scoped to the session's org."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.orgs.rbac import current_session
from apps.projects.forms import ProjectForm
from apps.projects.models import Project


def _organization(request):
    session = current_session(request)
    return session.organization if session else None


def _project(request, pk):
    org = _organization(request)
    if org is None:
        raise Http404("No organization.")
    return get_object_or_404(
        Project.objects.prefetch_related("campaigns"), pk=pk, organization=org
    )


@login_required
def project_list(request):
    org = _organization(request)
    projects = (
        org.projects.prefetch_related("campaigns")
        if org
        else Project.objects.none()
    )
    return render(request, "projects/list.html", {"projects": projects})


@login_required
@require_http_methods(["GET", "POST"])
def project_new(request):
    org = _organization(request)
    if org is None:
        messages.info(request, "A project belongs to an organization. Create one first.")
        return redirect("orgs")
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = Project.start(organization=org, **form.cleaned_data)
        messages.success(request, f"{project.title} created.")
        return redirect("project_detail", pk=project.pk)
    return render(request, "projects/new.html", {"form": form})


@login_required
def project_detail(request, pk):
    project = _project(request, pk)
    campaigns = project.campaigns.all()
    return render(
        request,
        "projects/detail.html",
        {"project": project, "campaigns": campaigns},
    )


@login_required
@require_POST
def project_delete(request, pk):
    project = _project(request, pk)
    title = project.title
    project.delete()
    messages.success(request, f"{title} deleted.")
    return redirect("projects")
