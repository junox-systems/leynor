"""Background work for the reel route. One task runs one step, then queues the next.

django-q2 routes by cluster name, and a task queued without one lands on the
caller's own cluster, so every enqueue names its cluster: Voice and Print go to
the heavy worker, everything else to the default one.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django_q.tasks import async_task

from apps.instagram.gates import HEAVY_STEPS, GateResult, Step
from apps.instagram.models import Reel, ReelPitch, RunStatus
from apps.instagram.runners import runner

log = logging.getLogger(__name__)


def cluster(heavy: bool = False) -> str:
    return f"{settings.APP_SLUG}-{'heavy' if heavy else 'default'}"


def queue_pitch(pitch: ReelPitch):
    async_task("apps.instagram.tasks.pitch", str(pitch.pk), cluster=cluster())


def queue_advance(reel: Reel):
    """Queue the reel's next step, if it is one the machine runs now."""
    gate = reel.current_gate
    if gate is None or not _runnable(gate):
        return
    async_task(
        "apps.instagram.tasks.advance",
        str(reel.pk),
        cluster=cluster(Step(gate.step) in HEAVY_STEPS),
    )


def _runnable(gate) -> bool:
    if gate.step == Step.IDEA or gate.status != RunStatus.IDLE:
        return False
    if gate.result == GateResult.REJECTED:
        return True  # a send-back re-runs the step with the note
    return not (gate.kind == "human" and gate.output)


def _message(exc: Exception) -> str:
    """What a person reads on the stopped step. The traceback goes to the log."""
    return str(exc) or f"{type(exc).__name__} with no message; see the worker log."


def _still_there(gate) -> bool:
    """The reel can be deleted while its step runs; then there is nothing to record."""
    return type(gate).objects.filter(pk=gate.pk).exists()


def pitch(pitch_id: str):
    pitch = ReelPitch.objects.select_related("campaign__audience").filter(pk=pitch_id).first()
    if pitch is None or pitch.reel_id or pitch.status != ReelPitch.Status.QUEUED:
        return
    pitch.status = ReelPitch.Status.RUNNING
    pitch.save(update_fields=["status", "updated_at"])
    try:
        concepts = runner(Step.IDEA)(pitch)
    except Exception as exc:
        log.exception("pitch %s failed", pitch_id)
        pitch.fail(_message(exc))
        return
    pitch.add_round(concepts)


def advance(reel_id: str):
    """Run the current step once. A pass queues the next; a person or a fault stops."""
    reel = (
        Reel.objects.select_related("campaign__project").filter(pk=reel_id).first()
    )
    if reel is None:
        return  # deleted while queued
    gate = reel.current_gate
    if gate is None or not _runnable(gate) or not gate.claim():
        return
    note = gate.note if gate.result == GateResult.REJECTED else ""
    try:
        output = runner(Step(gate.step))(reel, note)
    except Exception as exc:
        log.exception("reel %s step %s failed", reel_id, gate.step)
        if _still_there(gate):
            gate.fail(_message(exc))
        return
    if not _still_there(gate):
        return
    gate.finish(output)
    if gate.kind == "human":
        return  # a person judges it next
    gate.decide(GateResult.AUTO, None)
    queue_advance(reel)
