"""Drafting: one brief in, one generate-attack-revise run, one result.

The engine is schema-free and channel-free. The caller supplies the brief and
the instructions; nothing here knows what a Reel or a post is.
"""

from pydantic_ai import Agent

from apps.text.agents import DRAFTER, build_agents
from apps.text.graphs import run_draft
from apps.text.results import DraftResult


def draft(brief: str, *, model, instructions: str = "") -> DraftResult:
    agents = build_agents(model, instructions)
    return run_draft(brief, agents.deps())


def structured(
    brief: str, *, output_type, model, instructions: str = "", model_settings=None
):
    """One run that returns `output_type`. The caller owns the schema and picks the model."""
    system = f"{DRAFTER}\n\n{instructions}" if instructions else DRAFTER
    agent = Agent(
        model,
        system_prompt=system,
        output_type=output_type,
        model_settings=model_settings or None,
    )
    return agent.run_sync(brief).output
