"""pydantic-ai agents for the drafting steps.

No network at import time and no model resolution until a draft is requested:
`model=None` lets pydantic-ai read its own configuration from the environment.
"""

from dataclasses import dataclass

from pydantic_ai import Agent

from apps.text.graphs import DraftDeps

DRAFTER = (
    "You are the drafting half of a content production pipeline. Write only the "
    "artifact the brief asks for. Concrete, short, no preamble, no summary. "
    "Every number you use must come from the brief; if the brief lacks one, say "
    "so instead of inventing it."
)
CRITIC = (
    "You are the adversarial reviewer for a content production pipeline. State "
    "the single strongest objection to the draft, then the evidence that would "
    "answer it. If the draft has no shareable payoff, or cites a fact the brief "
    "does not support, say that first. Three sentences maximum."
)
REVISER = (
    "You rewrite a draft to answer a critique without changing what is true. "
    "Keep the length and format the draft already has. Return the rewritten "
    "artifact only."
)


@dataclass
class Agents:
    drafter: Agent
    critic: Agent
    reviser: Agent

    def deps(self) -> DraftDeps:
        return DraftDeps(
            generate=lambda brief: self.drafter.run_sync(brief).output,
            critique=lambda draft: self.critic.run_sync(draft).output,
            revise=lambda draft, critique: (
                self.reviser.run_sync(
                    f"Draft:\n{draft}\n\nCritique:\n{critique}"
                ).output
            ),
        )


def build_agents(model: str | None = None, skills: str = "") -> Agents:
    """Build the three agents. Model strings look like 'openai:gpt-5-mini'."""
    options: dict = {"defer_model_check": True}
    if model:
        options["model"] = model
    drafter = f"{DRAFTER}\n\n{skills}" if skills else DRAFTER
    return Agents(
        drafter=Agent(system_prompt=drafter, **options),
        critic=Agent(system_prompt=CRITIC, **options),
        reviser=Agent(system_prompt=REVISER, **options),
    )
