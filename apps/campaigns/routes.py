"""The gate vocabulary every channel route shares.

A route is data: one gate row per step, `current` is the first gate still open.
The step names are the channel's; this module only decides how a decision is
recorded and that decisions happen in order.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class GateResult(models.TextChoices):
    PENDING = "pending", "Pending"
    AUTO = "auto", "Passed automatically"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


DECIDED = (GateResult.APPROVED, GateResult.AUTO)
UNDECIDED = (GateResult.PENDING, GateResult.REJECTED)


class GateOutOfOrder(ValueError):
    """A gate was decided while an earlier step is still open."""


class RouteGate(BaseModel):
    """One decision on one step of one unit's route. Abstract: the channel types it."""

    step = models.CharField(max_length=16)
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

    class Meta:
        abstract = True
        ordering = ["position"]

    @property
    def unit(self):
        raise NotImplementedError("each route gate names its own unit FK")

    def __str__(self):
        return f"{self.unit.slug}: {self.get_step_display()}"

    def _require_current(self):
        current = self.unit.current_gate
        if current is None or current.pk != self.pk:
            raise GateOutOfOrder(f"{self.get_step_display()} is not the step in play.")

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
            update_fields=[
                "result",
                "note",
                "decided_by",
                "decided_at",
                "updated_at",
            ]
        )
