"""Drafting: one brief in, one generate-attack-revise run, one result.

The engine is schema-free and channel-free. The caller supplies the brief and
the instructions; nothing here knows what a Reel or a post is.
"""

from django.conf import settings

from apps.text.agents import build_agents
from apps.text.graphs import run_draft
from apps.text.results import DraftResult


def draft(brief: str, *, instructions: str = "") -> DraftResult:
    agents = build_agents(settings.APP_LLM_MODEL, instructions)
    return run_draft(brief, agents.deps())
