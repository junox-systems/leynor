"""Reel production: the step prompt, then the engine call. No ORM writes."""

from apps.instagram.gates import Step
from apps.instagram.steps import resolve
from apps.text.results import DraftResult
from apps.text.services import draft as text_draft
from apps.text.skills import read


class NotADraftingStep(ValueError):
    pass


def draft_step(step: Step, brief: str = "") -> DraftResult:
    """Draft the artifact one reel step asks for, with its skills as guidance."""
    spec = resolve(step)
    if not spec.llm:
        raise NotADraftingStep(f"{spec.id} is not a drafting step")
    return text_draft(
        brief or (spec.prompt or ""),
        instructions=read([*spec.skills, *spec.optional_skills]),
    )
