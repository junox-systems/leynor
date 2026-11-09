"""Reel pages: an idea becomes three concepts, a pick becomes a reel, the route runs.

Every view is org-scoped: another tenant's pitch, reel or file is a 404.
"""

import mimetypes
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.campaigns.models import Campaign
from apps.instagram.forms import PitchForm
from apps.instagram.gates import GateResult, Step
from apps.instagram.models import GateOutOfOrder, PitchError, Reel, ReelPitch
from apps.instagram.panels import pitch_payload, route_payload
from apps.instagram.services import kicker
from apps.instagram.tasks import queue_advance, queue_pitch
from apps.orgs.rbac import current_session
from apps.projects.models import Project
from apps.runs.artifacts import UnsafePath
from apps.video.design import DEFAULTS as REEL_DESIGN


def _organization(request):
    session = current_session(request)
    if session is None:
        raise Http404("No organization.")
    return session.organization


def _campaign(request, pk):
    return get_object_or_404(
        Campaign.objects.select_related("project__brand", "audience"),
        pk=pk,
        project__organization=_organization(request),
    )


def _reel(request, pk):
    # Scoped by organization: another tenant's reel is a 404, not a 403.
    return get_object_or_404(
        Reel.objects.select_related("campaign__project", "campaign__audience")
        .prefetch_related("gates"),
        pk=pk,
        campaign__project__organization=_organization(request),
    )


def _pitch(request, pk):
    return get_object_or_404(
        ReelPitch.objects.select_related("campaign__project__brand", "campaign__audience"),
        pk=pk,
        campaign__project__organization=_organization(request),
    )


@login_required
def reel_list(request):
    session = current_session(request)
    reels = (
        Reel.objects.filter(
            campaign__project__organization=session.organization,
            campaign__project__status=Project.Status.ACTIVE,
        )
        .select_related("campaign__project")
        .prefetch_related("gates")
        if session
        else Reel.objects.none()
    )
    pitches = (
        ReelPitch.objects.filter(
            campaign__project__organization=session.organization, reel__isnull=True
        ).select_related("campaign")
        if session
        else ReelPitch.objects.none()
    )
    return render(
        request, "instagram/list.html", {"reels": reels, "pitches": pitches}
    )


@login_required
@require_http_methods(["GET", "POST"])
def reel_new(request, campaign_pk):
    campaign = _campaign(request, campaign_pk)
    form = PitchForm(request.POST or None, campaign=campaign)
    if request.method == "POST" and form.is_valid():
        pitch = form.save()
        queue_pitch(pitch)
        return redirect("reel_pitch", pk=pitch.pk)
    return render(request, "instagram/new.html", {"form": form, "campaign": campaign})


@login_required
def pitch_detail(request, pk):
    pitch = _pitch(request, pk)
    if pitch.reel_id:
        return redirect("reel_detail", pk=pitch.reel_id)
    rounds = [
        {
            "index": index,
            "number": index + 1,
            "feedback": round_["feedback"],
            "concepts": [
                {
                    **concept,
                    "value": f"{index}:{n}",
                    "number": n + 1,
                    "count": len(concept["beats"]),
                }
                for n, concept in enumerate(round_["concepts"])
            ],
        }
        for index, round_ in enumerate(pitch.rounds)
    ]
    return render(
        request,
        "instagram/pitch.html",
        {
            "pitch": pitch,
            "campaign": pitch.campaign,
            "latest": rounds[-1] if rounds else None,
            "earlier": list(reversed(rounds[:-1])),
            "kicker": kicker(pitch.campaign),
            "design": REEL_DESIGN,
            "status": pitch_payload(pitch),
        },
    )


@login_required
@require_POST
def pitch_decide(request, pk):
    pitch = _pitch(request, pk)
    action = request.POST.get("action")
    note = request.POST.get("note", "").strip()[:500]
    try:
        if action == "pick":
            round_index, _, concept_index = request.POST.get("concept", "").partition(":")
            if not (round_index.isdigit() and concept_index.isdigit()):
                raise PitchError("Choose one of the takes first.")
            reel, created = pitch.pick(
                round_index=int(round_index),
                concept_index=int(concept_index),
                user=request.user,
                note=note,
            )
            if created:
                queue_advance(reel)
                messages.success(request, f"{reel.title} is on its way. Hook runs next.")
            return redirect("reel_detail", pk=reel.pk)
        if action == "again":
            if pitch.working:
                raise PitchError("Three takes are already being written.")
            pitch.start(note)
            queue_pitch(pitch)
        else:
            raise PitchError("Unknown action.")
    except PitchError as exc:
        messages.error(request, str(exc))
    return redirect("reel_pitch", pk=pitch.pk)


@login_required
def reel_detail(request, pk):
    reel = _reel(request, pk)
    route = reel.route()
    return render(
        request,
        "instagram/detail.html",
        {
            "reel": reel,
            "route": route,
            "spark": next(row for row in route if row["gate"].step == Step.IDEA),
            "scene_count": len(reel.spec.get("scenes", []))
            or len(route[0]["gate"].output.get("concept", {}).get("beats", [])),
            "kicker": kicker(reel.campaign),
            "design": REEL_DESIGN,
            "status": route_payload(reel),
        },
    )


@login_required
@require_POST
def gate_decide(request, pk, step):
    reel = _reel(request, pk)
    gate = get_object_or_404(reel.gates, step=step)
    name = gate.get_step_display()
    action = request.POST.get("action")
    note = request.POST.get("note", "").strip()[:500]
    try:
        if gate.kind != "human":
            raise ValidationError(f"{name} passes on its checks; nobody decides it.")
        if not gate.awaiting_person:
            raise ValidationError(f"{name} has nothing to decide yet.")
        if action == "approve":
            gate.decide(GateResult.APPROVED, request.user, note)
            messages.success(request, f"{name} approved.")
        elif action == "reject":
            if gate.step == Step.IDEA:
                raise ValidationError("Spark is chosen on the idea. Start a new idea instead.")
            if not note:
                raise ValidationError(f"Say what {name} should change, so the redo can follow it.")
            gate.decide(GateResult.REJECTED, request.user, note)
            messages.info(request, f"{name} sent back. Redoing it with your note.")
        else:
            raise ValidationError("Unknown action.")
    except (GateOutOfOrder, ValidationError) as exc:
        detail = getattr(exc, "messages", None)
        messages.error(request, " ".join(detail) if detail else str(exc))
        return redirect("reel_detail", pk=reel.pk)
    queue_advance(reel)
    return redirect("reel_detail", pk=reel.pk)


@login_required
@require_POST
def step_retry(request, pk, step):
    reel = _reel(request, pk)
    gate = get_object_or_404(reel.gates, step=step)
    try:
        gate.retry()
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        queue_advance(reel)
        messages.info(request, f"Trying {gate.get_step_display()} again.")
    return redirect("reel_detail", pk=reel.pk)


@login_required
def reel_media(request, pk, name):
    """One artifact of this reel: a visual, the voice, or the render."""
    reel = _reel(request, pk)
    store = reel.store()
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    try:  # a rerun or delete can remove the file mid-request
        response = _ranged(request, store, name, content_type) or FileResponse(
            store.open(name), content_type=content_type
        )
    except (UnsafePath, FileNotFoundError):
        raise Http404("No such file.") from None
    response["Accept-Ranges"] = "bytes"
    # Generated files only, but an SVG opened directly must never run script.
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    response["X-Content-Type-Options"] = "nosniff"
    return response


RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _ranged(request, store, name, content_type):
    """A 206 for one byte range: Safari will not play a video without it."""
    match = RANGE.match(request.headers.get("Range", ""))
    if not match or match.groups() == ("", ""):
        return None
    size = store.size(name)
    first, last = match.groups()
    if first:
        start, end = int(first), min(int(last) if last else size - 1, size - 1)
    else:  # "bytes=-N": the last N bytes
        start, end = max(size - int(last), 0), size - 1
    if start > end or start >= size:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{size}"
        return response
    # shortcut: S3File fetches the whole object before seek, fine for one reel's
    # files on the stack's network; use ranged GetObject if renders grow past ~100 MB.
    with store.open(name) as handle:
        handle.seek(start)
        body = handle.read(end - start + 1)
    response = HttpResponse(body, status=206, content_type=content_type)
    response["Content-Range"] = f"bytes {start}-{end}/{size}"
    return response


@login_required
@require_POST
def reel_delete(request, pk):
    reel = _reel(request, pk)
    title = reel.title
    campaign_pk = reel.campaign_id
    reel.delete()
    messages.success(request, f"{title} deleted.")
    return redirect("campaign_detail", pk=campaign_pk)
