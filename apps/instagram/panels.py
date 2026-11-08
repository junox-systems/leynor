"""Payloads for the route-status island. The views and the API share them."""

from django.urls import reverse

from apps.instagram.models import ReelPitch, RunStatus


def route_payload(reel) -> dict:
    """Where the route is now, plus a version that changes whenever a gate does."""
    gates = list(reel.gates.all())
    current = next((row for row in reel.route() if row["state"] not in ("passed",)), None)
    if current is None:
        status = "complete"
    elif current["gate"].status == RunStatus.RUNNING:
        status = "running"
    elif current["gate"].status == RunStatus.FAILED:
        status = "failed"
    elif current["gate"].awaiting_person:
        status = "waiting"
    else:
        status = "queued"
    gate = current["gate"] if current else None
    return {
        "kind": "reel",
        "status": status,
        "step": current["name"] if current else "",
        "started": gate.started_at.isoformat() if gate and gate.started_at else "",
        "error": gate.error if gate else "",
        "version": max((g.updated_at for g in gates)).isoformat() if gates else "",
        "urls": {
            "status": reverse("api-reel-route", args=[reel.pk]),
            "page": reverse("reel_detail", args=[reel.pk]),
        },
    }


def pitch_payload(pitch) -> dict:
    working = pitch.status in (ReelPitch.Status.QUEUED, ReelPitch.Status.RUNNING)
    return {
        "kind": "pitch",
        "status": "running" if working else pitch.status,
        "step": "Spark",
        "started": pitch.updated_at.isoformat() if working else "",
        "error": pitch.error,
        "version": pitch.updated_at.isoformat(),
        "urls": {
            "status": reverse("api-reel-pitch", args=[pitch.pk]),
            "page": reverse("reel_pitch", args=[pitch.pk]),
        },
    }
