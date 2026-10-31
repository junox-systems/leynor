"""The Reel route: six steps, and what a gate means for each of them.

A Reel is a video asset, so this route is Instagram's, not a shared one. The
gate mechanism itself lives in `apps.campaigns.routes`; only the step vocabulary
is here.
"""

from django.db import models

from apps.campaigns.routes import DECIDED, UNDECIDED, GateResult

__all__ = [
    "AUTO_GATES",
    "DECIDED",
    "HUMAN_GATES",
    "UNDECIDED",
    "GateResult",
    "Step",
    "gate_kind",
    "needs_human",
    "next_step",
]


class Step(models.TextChoices):
    IDEA = "idea", "Spark"
    HOOK = "hook", "Hook"
    BOARD = "board", "Board"
    LOOK = "look", "Look"
    VOICE = "voice", "Voice"
    PRINT = "print", "Print"


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
