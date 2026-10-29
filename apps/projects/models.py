"""A project is one Reel moving down one route of six gates.

The route is data, not code: Gate rows are created with the project, one per
Step, and `current` is simply the first gate still waiting for a decision.
Nothing stores the project's position, so a gate can never disagree with the
route it sits in.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from auditlog.registry import auditlog

from apps.core.models import BaseModel
from apps.projects.gates import GateResult, Step, gate_kind
from apps.projects.steps import resolve

# The steps a gate's result counts as decided.
DECIDED = (GateResult.APPROVED, GateResult.AUTO)
UNDECIDED = (GateResult.PENDING, GateResult.REJECTED)


class GateOutOfOrder(ValueError):
    """A gate was decided while an earlier step is still open."""


def _position(step: str) -> int:
    return list(Step).index(Step(step))


class Project(BaseModel):
    organization = models.ForeignKey(
        "orgs.Organization", on_delete=models.CASCADE, related_name="projects"
    )
    slug = models.SlugField(max_length=64)
    title = models.CharField(max_length=120)
    # A Reel is 60-120 seconds; the same window the spec enforces.
    target_seconds = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(60), MaxValueValidator(120)]
    )

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="unique_project_slug_per_org"
            )
        ]

    def __str__(self):
        return self.title

    @classmethod
    def start(cls, *, organization, title, slug, target_seconds=60):
        """Create the project and its six pending gates in one transaction."""
        with transaction.atomic():
            project = cls.objects.create(
                organization=organization,
                title=title,
                slug=slug,
                target_seconds=target_seconds,
            )
            project.gates.bulk_create(
                Gate(
                    project=project,
                    step=step,
                    position=_position(step),
                    kind=gate_kind(step),
                )
                for step in Step
            )
        return project

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
        """True when the open gate is a human one, or one already sent back."""
        gate = self.current_gate
        if gate is None:
            return False
        return gate.kind == "human" or gate.result == GateResult.REJECTED

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
            elif gate.result == GateResult.REJECTED:
                state, label, variant = "rejected", "Sent back", "destructive"
            elif current is not None and gate.pk == current.pk:
                state = "current"
                label, variant = (
                    ("Your call", "primary") if human else ("Ready", "outline")
                )
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
        return (
            f"{name} sent back" if gate.result == GateResult.REJECTED else f"On {name}"
        )


class Gate(BaseModel):
    """One decision on one step. Exactly one row per project and step."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="gates")
    step = models.CharField(max_length=16, choices=Step.choices)
    position = models.PositiveSmallIntegerField(editable=False)
    kind = models.CharField(max_length=8, default="auto")
    result = models.CharField(
        max_length=8, choices=GateResult.choices, default=GateResult.PENDING
    )
    note = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "step"], name="one_gate_per_step"
            )
        ]

    def __str__(self):
        return f"{self.project.slug}: {self.get_step_display()}"

    def _require_current(self):
        current = self.project.current_gate
        if current is None or current.pk != self.pk:
            raise GateOutOfOrder(f"{resolve(self.step).name} is not the step in play.")

    def decide(self, result, user, note=""):
        """Record a decision on this gate, if it is the route's current step."""
        if result not in (GateResult.APPROVED, GateResult.AUTO, GateResult.REJECTED):
            raise ValidationError("A gate is passed, marked auto, or sent back.")
        self._require_current()
        self.result = result
        self.note = note.strip()
        self.decided_by = user
        self.decided_at = timezone.now()
        self.save(
            update_fields=["result", "note", "decided_by", "decided_at", "updated_at"]
        )

    def reopen(self):
        """Put a sent-back gate back in play."""
        if self.result != GateResult.REJECTED:
            raise ValidationError("Only a gate that was sent back can be reopened.")
        self.result = GateResult.PENDING
        self.note = ""
        self.decided_by = None
        self.decided_at = None
        self.save(
            update_fields=["result", "note", "decided_by", "decided_at", "updated_at"]
        )


auditlog.register(Project)
auditlog.register(Gate)
