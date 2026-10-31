"""The Reel: Instagram's video unit, its six gates, and its spec.

A Reel is an output unit of a campaign, so it inherits the campaign's tenancy.
The route is data: one `ReelGate` row per step, and `current_gate` is the first
one still open. Nothing stores the reel's position.
"""

from pydantic import ValidationError as PydanticValidationError

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction

from apps.campaigns.models import Unit
from apps.campaigns.routes import (
    DECIDED,
    GateOutOfOrder,
    GateResult,
    RouteGate,
)
from apps.core.models import BaseModel
from apps.instagram.gates import Step, gate_kind
from apps.instagram.steps import resolve
from apps.video.spec import ReelSpec

__all__ = ["GateOutOfOrder", "GateResult", "Reel", "ReelGate"]


def _position(step: str) -> int:
    return list(Step).index(Step(step))


class Reel(Unit):
    # A Reel is 60-120 seconds; the same window the spec enforces.
    target_seconds = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(60), MaxValueValidator(120)]
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
    def start(cls, *, campaign, title, slug, target_seconds=60):
        """Create the reel and its six pending gates in one transaction."""
        with transaction.atomic():
            reel = cls.objects.create(
                campaign=campaign,
                title=title,
                slug=slug,
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


class ReelGate(RouteGate):
    """One decision on one step of a reel. Exactly one row per reel and step."""

    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="gates")
    step = models.CharField(max_length=16, choices=Step.choices)

    class Meta(RouteGate.Meta):
        constraints = [
            models.UniqueConstraint(fields=["reel", "step"], name="one_gate_per_reel")
        ]

    @property
    def unit(self):
        return self.reel
