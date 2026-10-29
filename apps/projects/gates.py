"""The six steps, and what a gate means for each of them.

One vocabulary for the whole app: the route order is `Step` definition order, and
whether a step needs a person is decided here, not in a view or a template.
"""

from django.db import models


class Step(models.TextChoices):
    IDEA = "idea", "Spark"
    HOOK = "hook", "Hook"
    BOARD = "board", "Board"
    LOOK = "look", "Look"
    VOICE = "voice", "Voice"
    PRINT = "print", "Print"


class GateResult(models.TextChoices):
    PENDING = "pending", "Pending"
    AUTO = "auto", "Passed automatically"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


# A person decides these; everything else passes on evidence.
HUMAN_GATES = frozenset({Step.BOARD, Step.PRINT})
AUTO_GATES = frozenset(Step) - HUMAN_GATES


def needs_human(step: Step) -> bool:
    return step in HUMAN_GATES


def next_step(step: Step) -> Step | None:
    steps = list(Step)
    index = steps.index(step)
    return steps[index + 1] if index + 1 < len(steps) else None


def gate_kind(step: Step) -> str:
    return "human" if needs_human(step) else "auto"
