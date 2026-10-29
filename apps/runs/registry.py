"""Step to runner. Imported lazily so the web process never loads torch."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from apps.projects.gates import Step

RUNNERS: dict[Step, tuple[str, str]] = {
    Step.IDEA: ("apps.creative.services", "draft"),
    Step.HOOK: ("apps.creative.services", "draft"),
    Step.BOARD: ("apps.creative.services", "draft"),
    Step.LOOK: ("apps.renders.services", "run_look"),
    Step.VOICE: ("apps.voices.services", "run_voice"),
    Step.PRINT: ("apps.renders.services", "run_print"),
}


class NoRunner(RuntimeError):
    pass


def runner(step: Step) -> Callable:
    try:
        module_name, attribute = RUNNERS[step]
    except KeyError:
        raise NoRunner(f"no runner registered for {step}") from None
    return getattr(import_module(module_name), attribute)
