"""Drafting: one step, one pydantic-ai graph run, one result. No ORM."""

from django.conf import settings

from apps.creative.agents import build_agents
from apps.creative.graphs import run_draft
from apps.creative.results import DraftResult
from apps.creative.skills import read
from apps.projects.gates import Step
from apps.projects.steps import resolve


class NotADraftingStep(ValueError):
    pass


def draft(step: Step, brief: str = "") -> DraftResult:
    spec = resolve(step)
    if not spec.llm:
        raise NotADraftingStep(f"{spec.id} is not a drafting step")
    agents = build_agents(settings.LEYNOR_LLM_MODEL, read(spec, optional=True))
    return run_draft(spec.id, brief or (spec.prompt or ""), agents.deps())
