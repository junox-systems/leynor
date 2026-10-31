"""Step to engine call. Imported lazily so the web process stays light."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from apps.instagram.gates import Step

RUNNERS: dict[Step, tuple[str, str]] = {
    Step.IDEA: ("apps.instagram.services", "draft_step"),
    Step.HOOK: ("apps.instagram.services", "draft_step"),
    Step.BOARD: ("apps.instagram.services", "draft_step"),
    Step.LOOK: ("apps.image.services", "generate"),
    Step.VOICE: ("apps.video.audio.services", "run_voice"),
    Step.PRINT: ("apps.video.services", "run_print"),
}


class NoRunner(RuntimeError):
    pass


def runner(step: Step) -> Callable:
    try:
        module_name, attribute = RUNNERS[step]
    except KeyError:
        raise NoRunner(f"no runner registered for {step}") from None
    return getattr(import_module(module_name), attribute)
