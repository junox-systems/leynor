"""The draft graph: generate, attack, revise.

The graph is deterministic and dependency-injected, so it runs in tests without a
model. `agents.py` supplies the real pydantic-ai calls.
"""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_graph import Graph, GraphBuilder, StepContext

from apps.creative.results import DraftResult
from apps.projects.gates import Step


class DraftState(BaseModel):
    step: Step
    brief: str
    draft: str = ""
    critique: str = ""


class Drafted(BaseModel):
    text: str


class Critiqued(BaseModel):
    draft: str
    critique: str


@dataclass
class DraftDeps:
    """Three callables; pydantic-ai agents in production, fakes in tests."""

    generate: Callable[[str], str]
    critique: Callable[[str], str]
    revise: Callable[[str, str], str]


def build_draft_graph() -> Graph[DraftState, DraftDeps, None, DraftResult]:
    builder = GraphBuilder(
        name="reel-draft",
        state_type=DraftState,
        deps_type=DraftDeps,
        output_type=DraftResult,
    )

    async def generate(ctx: StepContext[DraftState, DraftDeps, None]) -> Drafted:
        ctx.state.draft = ctx.deps.generate(ctx.state.brief)
        return Drafted(text=ctx.state.draft)

    async def critique(ctx: StepContext[DraftState, DraftDeps, Drafted]) -> Critiqued:
        ctx.state.critique = ctx.deps.critique(ctx.inputs.text)
        return Critiqued(draft=ctx.state.draft, critique=ctx.state.critique)

    async def revise(ctx: StepContext[DraftState, DraftDeps, Critiqued]) -> DraftResult:
        revised = ctx.deps.revise(ctx.inputs.draft, ctx.inputs.critique)
        return DraftResult(
            step=ctx.state.step,
            draft=ctx.state.draft,
            critique=ctx.state.critique,
            revised=revised,
            revisions=1,
        )

    generate_node = builder.step(generate)
    critique_node = builder.step(critique)
    revise_node = builder.step(revise)

    builder.add_edge(builder.start_node, generate_node)
    builder.add_edge(generate_node, critique_node)
    builder.add_edge(critique_node, revise_node)
    builder.add_edge(revise_node, builder.end_node)
    return builder.build()


def run_draft(step: Step, brief: str, deps: DraftDeps) -> DraftResult:
    graph = build_draft_graph()
    state = DraftState(step=step, brief=brief)
    return graph.run_sync(state=state, deps=deps)
