"""The Reel: Instagram's video unit, its six gates, and its spec.

A Reel is an output unit of a campaign, so it inherits the campaign's tenancy.
The route is data: one `ReelGate` row per step, and `current_gate` is the first
one still open. Nothing stores the reel's position.
"""

import logging

from pydantic import ValidationError as PydanticValidationError

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

from apps.campaigns.models import Goal, PublicationBase, Unit
from apps.campaigns.routes import (
    DECIDED,
    GateOutOfOrder,
    GateResult,
    RouteGate,
)
from apps.core.models import BaseModel
from apps.instagram.gates import Step, gate_kind
from apps.instagram.steps import resolve
from apps.runs.artifacts import ArtifactStore
from apps.video.spec import ReelSpec

log = logging.getLogger(__name__)

__all__ = [
    "GateOutOfOrder",
    "GateResult",
    "InstagramPublication",
    "Reel",
    "ReelGate",
    "ReelPitch",
    "RunStatus",
]


class RunStatus(models.TextChoices):
    """Where the engine is on one step, beside the gate's decision."""

    IDLE = "idle", "Idle"
    RUNNING = "running", "Running"
    FAILED = "failed", "Failed"


def _position(step: str) -> int:
    return list(Step).index(Step(step))


def _unique_slug(campaign, title: str) -> str:
    """A stable key from the title, numbered when the campaign already has one."""
    base = (slugify(title) or "reel")[:56]
    taken = set(
        Reel.objects.filter(campaign=campaign, slug__startswith=base).values_list(
            "slug", flat=True
        )
    )
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


class Reel(Unit):
    # The spec, the visual seed and the render file names are keyed by slug.
    # Derived from the title, so no one types it.
    slug = models.SlugField(max_length=64)
    # A Reel is 60-180 seconds; the same window the spec enforces. Over 180
    # Instagram stops recommending it to new audiences.
    target_seconds = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(60), MaxValueValidator(180)],
        help_text="60 to 180 seconds.",
    )
    # Validated `ReelSpec` output. Empty until the storyboard step writes it.
    spec = models.JSONField(default=dict, blank=True)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "slug"], name="unique_reel_slug_per_campaign"
            )
        ]

    @classmethod
    def create(cls, *, campaign, title, prompt="", goal="", target_seconds=60, slug=None):
        """Create the reel and its six pending gates in one transaction."""
        with transaction.atomic():
            reel = cls.objects.create(
                campaign=campaign,
                title=title,
                prompt=prompt,
                goal=goal,
                slug=slug or _unique_slug(campaign, title),
                target_seconds=target_seconds,
            )
            reel.gates.bulk_create(
                ReelGate(
                    reel=reel,
                    step=step,
                    position=_position(step),
                    kind=gate_kind(step),
                )
                for step in Step
            )
        return reel

    def clean(self):
        if not self.spec:
            return
        try:
            ReelSpec.model_validate(self.spec)
        except PydanticValidationError as exc:
            raise ValidationError({"spec": str(exc)}) from None

    @property
    def has_route(self) -> bool:
        return True

    @property
    def current_gate(self):
        """The first gate still open, or None when every step has passed."""
        return self.gates.exclude(result__in=DECIDED).first()

    @property
    def complete(self) -> bool:
        return self.current_gate is None

    @property
    def passed(self) -> int:
        return self.gates.filter(result__in=DECIDED).count()

    @property
    def percent(self) -> int:
        return round(self.passed * 100 / len(Step))

    @property
    def needs_person(self) -> bool:
        """True when the open gate waits on a decision or a retry."""
        gate = self.current_gate
        if gate is None:
            return False
        return gate.awaiting_person or gate.status == RunStatus.FAILED

    def store(self) -> ArtifactStore:
        """This reel's artifacts: org/project/campaign/reel/<key> in the artifacts storage."""
        campaign = self.campaign
        return ArtifactStore(
            "/".join(
                str(part)
                for part in (campaign.project.organization_id, campaign.project_id, campaign.pk, self.pk)
            )
        )

    def route(self):
        """Every step in order, with the state a template renders.

        Keys: spec (StepSpec), gate, state, current, human, label, variant.
        """
        current = self.current_gate
        rows = []
        for gate in self.gates.all():
            human = gate.kind == "human"
            if gate.result in DECIDED:
                state, label, variant = "passed", "Passed", "secondary"
            elif gate.status == RunStatus.RUNNING:
                state, label, variant = "running", "Running", "outline"
            elif gate.status == RunStatus.FAILED:
                state, label, variant = "failed", "Stopped", "destructive"
            elif gate.result == GateResult.REJECTED:
                state, label, variant = "rejected", "Sent back", "destructive"
            elif current is not None and gate.pk == current.pk:
                if gate.awaiting_person:
                    state, label, variant = "current", "Your call", "primary"
                else:
                    state, label, variant = "queued", "Queued", "outline"
            else:
                state, label, variant = "waiting", "Waiting", "outline"
            rows.append(
                {
                    "spec": resolve(gate.step),
                    "name": gate.get_step_display(),
                    "gate": gate,
                    "state": state,
                    "current": current is not None and gate.pk == current.pk,
                    "human": human,
                    "label": label,
                    "variant": variant,
                }
            )
        return rows

    def summary(self) -> str:
        """One line for a list row: where the reel sits right now."""
        if self.complete:
            return "Complete"
        gate = self.current_gate
        name = gate.get_step_display()
        if gate.status == RunStatus.RUNNING:
            return f"Running {name}"
        if gate.status == RunStatus.FAILED:
            return f"{name} stopped"
        if gate.result == GateResult.REJECTED:
            return f"{name} sent back"
        return f"{name}: your call" if gate.awaiting_person else f"On {name}"


class ReelGate(RouteGate):
    """One decision on one step of a reel. Exactly one row per reel and step."""

    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="gates")
    step = models.CharField(max_length=16, choices=Step.choices)
    # What the engine produced for this step. shortcut: latest attempt only; add
    # a StepRun history table when someone needs to compare attempts.
    output = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=8, choices=RunStatus.choices, default=RunStatus.IDLE
    )
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)

    class Meta(RouteGate.Meta):
        constraints = [
            models.UniqueConstraint(fields=["reel", "step"], name="one_gate_per_reel")
        ]

    @property
    def unit(self):
        return self.reel

    @property
    def awaiting_person(self) -> bool:
        """A human gate with something to judge. Spark is judged on the pitch."""
        return (
            self.kind == "human"
            and self.result == GateResult.PENDING
            and self.status == RunStatus.IDLE
            and (bool(self.output) or self.step == Step.IDEA)
        )

    def claim(self) -> bool:
        """Mark this gate running, unless another worker already holds it."""
        now = timezone.now()
        claimed = (
            ReelGate.objects.filter(pk=self.pk)
            .exclude(status=RunStatus.RUNNING)
            .update(status=RunStatus.RUNNING, error="", started_at=now, updated_at=now)
        )
        if claimed:
            self.status, self.error, self.started_at = RunStatus.RUNNING, "", now
        return bool(claimed)

    def finish(self, output: dict):
        """Keep what the step made. A re-run after a send-back is judged again."""
        self.output = output
        self.status = RunStatus.IDLE
        fields = ["output", "status", "updated_at"]
        if self.result == GateResult.REJECTED:
            self.result = GateResult.PENDING
            self.decided_by = None
            self.decided_at = None
            fields += ["result", "decided_by", "decided_at"]
        self.save(update_fields=fields)

    def fail(self, error: str):
        self.status = RunStatus.FAILED
        self.error = error[:2000]
        self.save(update_fields=["status", "error", "updated_at"])

    def retry(self):
        """Put a stopped step back in the queue."""
        if self.status != RunStatus.FAILED:
            raise ValidationError("Only a stopped step can be tried again.")
        self.status = RunStatus.IDLE
        self.error = ""
        self.save(update_fields=["status", "error", "updated_at"])


class PitchError(ValueError):
    """A pitch could not be picked as asked."""


class ReelPitch(BaseModel):
    """One idea and the rounds of three concepts drafted from it.

    No reel exists until a person picks a concept, so `Reel.create` keeps its
    invariants: a title, a derived slug, six gates.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Writing"
        READY = "ready", "Ready"
        FAILED = "failed", "Stopped"

    campaign = models.ForeignKey(
        "campaigns.Campaign", on_delete=models.CASCADE, related_name="reel_pitches"
    )
    idea = models.TextField(help_text="What the reel is about, in your words.")
    goal = models.CharField(
        max_length=8,
        choices=Goal.choices,
        help_text="The one outcome the reel chases.",
    )
    target_seconds = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(60), MaxValueValidator(180)],
        help_text="60 to 180 seconds.",
    )
    # [{"feedback": str, "concepts": [concept dict, ...]}], oldest first.
    rounds = models.JSONField(default=list, blank=True)
    # The note that asked for the round being written now.
    feedback = models.TextField(blank=True)
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.QUEUED
    )
    error = models.TextField(blank=True)
    reel = models.OneToOneField(
        Reel, null=True, blank=True, on_delete=models.SET_NULL, related_name="pitch"
    )

    class Meta(BaseModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return self.idea[:60]

    @property
    def organization(self):
        return self.campaign.organization

    @property
    def working(self) -> bool:
        return self.status in (self.Status.QUEUED, self.Status.RUNNING)

    @property
    def latest(self) -> dict | None:
        return self.rounds[-1] if self.rounds else None

    def start(self, feedback: str = ""):
        """Queue a new round. The note steers it; earlier rounds stay."""
        if self.reel_id:
            raise PitchError("This idea already became a reel.")
        self.feedback = feedback.strip()
        self.status = self.Status.QUEUED
        self.error = ""
        self.save(update_fields=["feedback", "status", "error", "updated_at"])

    def add_round(self, concepts: list[dict]):
        self.rounds = [*self.rounds, {"feedback": self.feedback, "concepts": concepts}]
        self.status = self.Status.READY
        self.feedback = ""
        self.save(update_fields=["rounds", "status", "feedback", "updated_at"])

    def fail(self, error: str):
        self.status = self.Status.FAILED
        self.error = error[:2000]
        self.save(update_fields=["status", "error", "updated_at"])

    def pick(self, *, round_index: int, concept_index: int, user, note: str = ""):
        """Turn one concept into a reel with Spark decided. Returns (reel, created)."""
        with transaction.atomic():
            pitch = ReelPitch.objects.select_for_update().get(pk=self.pk)
            if pitch.reel_id:
                return pitch.reel, False
            try:
                concepts = pitch.rounds[round_index]["concepts"]
                concept = concepts[concept_index]
            except (IndexError, KeyError, TypeError):
                raise PitchError("That concept is not on this pitch.") from None
            reel = Reel.create(
                campaign=pitch.campaign,
                title=concept["title"][:120],
                prompt=pitch.idea,
                goal=pitch.goal,
                target_seconds=pitch.target_seconds,
            )
            spark = reel.gates.get(step=Step.IDEA)
            spark.output = {
                "concept": concept,
                "alternatives": [
                    {"title": other["title"], "rejected": "Not picked"}
                    for index, other in enumerate(concepts)
                    if index != concept_index
                ],
                "note": note.strip(),
            }
            spark.save(update_fields=["output", "updated_at"])
            spark.decide(
                GateResult.APPROVED, user, note or f"Picked “{reel.title}”."
            )
            pitch.reel = reel
            pitch.save(update_fields=["reel", "updated_at"])
        self.reel = reel
        return reel, True


class InstagramPublication(PublicationBase):
    """One posted instance of a reel on an Instagram account."""

    reel = models.ForeignKey(
        Reel, on_delete=models.CASCADE, related_name="publications"
    )

    class Meta:
        ordering = ["-published_at", "-created_at"]


@receiver(post_delete, sender=Reel)
def delete_artifacts(sender, instance, **kwargs):
    """A deleted reel takes its files with it, once the delete is committed."""
    store = instance.store()

    def remove():
        try:
            store.delete_all()
        except Exception:  # the row is gone either way; leftovers only cost space
            log.exception("could not delete artifacts under %s", store.prefix)

    transaction.on_commit(remove)
