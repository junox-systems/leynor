"""Step to engine call. Imported lazily so the web process stays light."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from apps.instagram.gates import Step

# Spark is drafted on the pitch, before a reel exists; the rest take (reel, note).
RUNNERS: dict[Step, tuple[str, str]] = {
    Step.IDEA: ("apps.instagram.services", "pitch_concepts"),
    Step.HOOK: ("apps.instagram.services", "hooks_step"),
    Step.BOARD: ("apps.instagram.services", "board_step"),
    Step.LOOK: ("apps.instagram.services", "look_step"),
    Step.VOICE: ("apps.instagram.services", "voice_step"),
    Step.PRINT: ("apps.instagram.services", "print_step"),
}


class NoRunner(RuntimeError):
    pass


def runner(step: Step) -> Callable:
    try:
        module_name, attribute = RUNNERS[step]
    except KeyError:
        raise NoRunner(f"no runner registered for {step}") from None
    return getattr(import_module(module_name), attribute)
