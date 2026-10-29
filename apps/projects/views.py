"""Reels and their gate decisions. Every view is scoped to the session's org."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.orgs.rbac import current_session
from apps.projects.forms import ProjectForm
from apps.projects.gates import GateResult
from apps.projects.models import GateOutOfOrder, Project


def _organization(request):
    session = current_session(request)
    return session.organization if session else None


def _project(request, pk):
    org = _organization(request)
    if org is None:
        raise Http404("No organization.")
    # Scoped by organization: another tenant's reel is a 404, not a 403.
    return get_object_or_404(
        Project.objects.prefetch_related("gates"), pk=pk, organization=org
    )


@login_required
def project_list(request):
    org = _organization(request)
    projects = org.projects.prefetch_related("gates") if org else Project.objects.none()
    return render(request, "projects/list.html", {"projects": projects})


@login_required
@require_http_methods(["GET", "POST"])
def project_new(request):
    org = _organization(request)
    if org is None:
        messages.info(request, "A reel belongs to an organization. Create one first.")
        return redirect("orgs")
    form = ProjectForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        project = Project.start(organization=org, **form.cleaned_data)
        messages.success(request, f"{project.title} started on Spark.")
        return redirect("project_detail", pk=project.pk)
    return render(request, "projects/new.html", {"form": form})


@login_required
def project_detail(request, pk):
    project = _project(request, pk)
    return render(
        request, "projects/detail.html", {"project": project, "route": project.route()}
    )


@login_required
@require_POST
def gate_decide(request, pk, step):
    project = _project(request, pk)
    gate = get_object_or_404(project.gates, step=step)
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
    return redirect("project_detail", pk=project.pk)


@login_required
@require_POST
def project_delete(request, pk):
    project = _project(request, pk)
    title = project.title
    project.delete()
    messages.success(request, f"{title} deleted.")
    return redirect("projects")
