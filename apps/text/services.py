"""Drafting: one brief in, one generate-attack-revise run, one result.

The engine is schema-free and channel-free. The caller supplies the brief and
the instructions; nothing here knows what a Reel or a post is.
"""

from django.conf import settings
from pydantic_ai import Agent

from apps.text.agents import DRAFTER, build_agents
from apps.text.graphs import run_draft
from apps.text.results import DraftResult


class NoModel(RuntimeError):
    """No language model is configured."""


def draft(brief: str, *, instructions: str = "") -> DraftResult:
    agents = build_agents(settings.APP_LLM_MODEL, instructions)
    return run_draft(brief, agents.deps())


def structured(brief: str, *, output_type, instructions: str = "", model=None):
    """One run that returns `output_type`. The caller owns the schema."""
    model = model or settings.APP_LLM_MODEL
    if not model:
        raise NoModel("No language model is configured. Set APP_LLM_MODEL.")
    system = f"{DRAFTER}\n\n{instructions}" if instructions else DRAFTER
    agent = Agent(model, system_prompt=system, output_type=output_type)
    return agent.run_sync(brief).output
