"""Reel production: briefs, schemas and checks for each drafting step.

The text engine returns the schema these functions name; the validators decide
whether the result is good enough. Nothing here writes a row: `tasks` does.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic import ValidationError as SchemaError

from apps.instagram.gates import Step
from apps.instagram.steps import resolve
from apps.instagram.validators import (
    ARCHETYPES,
    WORDS_PER_SECOND,
    overlay_words,
    validate_beats,
    validate_hooks,
    validate_idea,
)
from apps.text.services import structured
from apps.text.skills import read
from apps.video.spec import ReelSpec, SceneSpec

ATTEMPTS = 2  # one draft, one revision that is told what failed


class StepFailed(RuntimeError):
    """A step's output did not pass its checks. The message is for a person."""


# -- schemas the model fills ---------------------------------------------------


class Citation(BaseModel):
    claim: str = Field(description="What the input says, quoted or closely paraphrased.")
    source: Literal["idea", "audience"] = Field(
        description="'idea' for the operator's idea, 'audience' for the audience notes."
    )


class Hook(BaseModel):
    archetype: str = Field(description=f"One of: {', '.join(sorted(ARCHETYPES))}.")
    spoken: str = Field(description="The first spoken line.")
    first_frame: str = Field(description="What is on screen in frame one.")
    overlay: str = Field(description="On-screen text, 3 to 7 words, 44 characters max.")
    objection: str = ""
    answer: str = ""


class Beat(BaseModel):
    name: str
    purpose: str = Field(description="hook, setup, turn, proof or payoff.")
    seconds: float


class Concept(BaseModel):
    title: str = Field(description="A working title, under 60 characters.")
    sentence: str = Field(description="The idea in one sentence, 20 to 180 characters.")
    insight: str = Field(
        description="'<audience> wants <X>, but <Y> stands in the way, because <Z>.'"
    )
    score: float = Field(description="HumanKind score 0-10; be honest.")
    citations: list[Citation]
    hook: Hook
    beats: list[Beat] = Field(description="2 to 8 beats; first is the hook.")
    objection: str = Field(description="The strongest objection to this concept.")
    answer: str = Field(description="Why the concept survives the objection.")


class ConceptSet(BaseModel):
    concepts: list[Concept]


class HookSet(BaseModel):
    hooks: list[Hook]


class BoardScene(BaseModel):
    name: str
    purpose: str = Field(description="hook, setup, turn, proof or payoff.")
    narration: str = Field(description="What the voice says in this scene.")
    overlay: str = Field(description="On-screen text, 44 characters max.")
    label: str = Field(description="Two to four words naming the visual.")
    visual_beat: str = Field(description="What the viewer sees happen.")
    seconds: float


class Board(BaseModel):
    scenes: list[BoardScene]


# -- briefs --------------------------------------------------------------------


def _audience_lines(audience) -> list[str]:
    if audience is None:
        return ["Audience: none recorded. Cite only the idea."]
    lines = [f"Audience: {audience.name}"]
    for label, value in (
        ("Who they are", audience.description),
        ("They want", audience.wants),
        ("In their way", audience.barrier),
    ):
        if value:
            lines.append(f"{label}: {value}")
    return lines


def pitch_brief(pitch) -> str:
    campaign = pitch.campaign
    lines = [
        "Write three distinct concepts for one Instagram Reel.",
        f"Idea: {pitch.idea}",
        f"Primary goal: {pitch.goal}",
        f"Length: {pitch.target_seconds} seconds",
        *_audience_lines(campaign.audience),
    ]
    if campaign.goal:
        lines.append(f"Campaign goal: {campaign.goal}")
    for number, round_ in enumerate(pitch.rounds, start=1):
        titles = "; ".join(c["title"] for c in round_["concepts"])
        lines.append(f"Round {number} offered: {titles}. Do not repeat them.")
    if pitch.feedback:
        lines.append(f"The person asked for this change: {pitch.feedback}")
    lines += [
        "Each concept needs a different hook archetype and a different angle.",
        "Cite only the idea or the audience notes above. Never invent a statistic,",
        "a study, a quote or a source.",
    ]
    return "\n".join(lines)


def _skills(*steps: Step) -> str:
    names = []
    for step in steps:
        spec = resolve(step)
        names += [*spec.skills, *spec.optional_skills]
    return read(names)


# -- checks --------------------------------------------------------------------


def hook_problems(hook: dict, label: str = "hook") -> list[str]:
    problems = []
    if hook.get("archetype") not in ARCHETYPES:
        problems.append(f"{label} archetype must be one of {', '.join(sorted(ARCHETYPES))}")
    for field in ("spoken", "first_frame", "overlay"):
        if not str(hook.get(field, "")).strip():
            problems.append(f"{label} is missing {field}")
    overlay = str(hook.get("overlay", "")).strip()
    if overlay and not 3 <= overlay_words(overlay) <= 7:
        problems.append(f"{label} overlay must be 3 to 7 words")
    if len(overlay) > 44:
        problems.append(f"{label} overlay is over 44 characters")
    return problems


def idea_record(concept: dict, goal: str, alternatives: list[dict]) -> dict:
    """The Spark record `validate_idea` reads."""
    return {
        "sentence": concept["sentence"],
        "insight": concept["insight"],
        "goal": goal,
        "score": concept["score"],
        "citations": concept["citations"],
        "alternatives": alternatives,
        "adversarial": {"objection": concept["objection"], "answer": concept["answer"]},
    }


def concept_problems(concepts: list[dict], goal: str, has_audience: bool) -> list[str]:
    if len(concepts) != 3:
        return [f"wrote {len(concepts)} concepts; exactly three are needed"]
    problems = []
    for index, concept in enumerate(concepts, start=1):
        others = [
            {"title": other["title"], "rejected": "pitched alongside"}
            for other in concepts
            if other is not concept
        ]
        found = validate_idea(idea_record(concept, goal, others))
        found += hook_problems(concept["hook"])
        if not has_audience and any(
            c["source"] == "audience" for c in concept["citations"]
        ):
            found.append("cites an audience, but the campaign has none")
        if not 2 <= len(concept["beats"]) <= 8:
            found.append("needs 2 to 8 beats")
        problems += [f"concept {index}: {problem}" for problem in found]
    return problems


# -- the steps -----------------------------------------------------------------


def _attempt(brief: str, output_type, instructions: str, check):
    """Draft, check, and redraft once with the failures named."""
    problems: list[str] = []
    for _ in range(ATTEMPTS):
        steer = (
            "\n\nThe last attempt failed these checks; fix every one:\n- "
            + "\n- ".join(problems)
            if problems
            else ""
        )
        result = structured(brief + steer, output_type=output_type, instructions=instructions)
        value, problems = check(result)
        if not problems:
            return value
    raise StepFailed("; ".join(problems[:6]))


def pitch_concepts(pitch) -> list[dict]:
    """Three checked concepts for one idea."""
    has_audience = pitch.campaign.audience_id is not None

    def check(result: ConceptSet):
        concepts = [concept.model_dump() for concept in result.concepts]
        return concepts, concept_problems(concepts, pitch.goal, has_audience)

    return _attempt(pitch_brief(pitch), ConceptSet, _skills(Step.IDEA, Step.HOOK), check)


def kicker(campaign) -> str:
    """The line across the top of every frame: the brand, else the campaign."""
    brand = campaign.project.brand
    return (brand.name if brand else campaign.title).upper()


def _spark(reel) -> dict:
    return reel.gates.get(step=Step.IDEA).output.get("concept") or {}


def _steer(reel, note: str) -> str:
    """The note given with the pick, and the one given with a send-back."""
    lines = []
    picked = reel.gates.get(step=Step.IDEA).output.get("note")
    if picked:
        lines.append(f"\nThe person picked this concept with a note; keep it in mind: {picked}")
    if note:
        lines.append(f"\nThe person sent this step back with a note; follow it: {note}")
    return "".join(lines)


def hooks_step(reel, note: str = "") -> dict:
    """The picked hook stays the winner; the model writes the alternates."""
    concept = _spark(reel)
    if not concept:
        raise StepFailed("Spark has no picked concept, so there is no hook to keep.")
    pinned = {**concept["hook"], "chosen": True}
    pinned["objection"] = pinned.get("objection") or concept["objection"]
    pinned["answer"] = pinned.get("answer") or concept["answer"]
    brief = "\n".join(
        [
            f"Concept: {concept['sentence']}",
            f"Insight: {concept['insight']}",
            f"The winning hook is fixed: \"{pinned['spoken']}\" / overlay \"{pinned['overlay']}\".",
            "Write six alternates across at least three archetypes, each with a spoken",
            "line, first frame and a 3-7 word overlay. They are the record of what was",
            "considered, not replacements." + _steer(reel, note),
        ]
    )

    def check(result: HookSet):
        rows = [pinned] + [
            {**hook.model_dump(), "chosen": False} for hook in result.hooks
        ]
        return {"hooks": rows}, validate_hooks(rows)

    return _attempt(brief, HookSet, _skills(Step.HOOK), check)


def board_step(reel, note: str = "") -> dict:
    """Scenes with narration sized to the target length, written to `reel.spec`."""
    concept = _spark(reel)
    hooks = reel.gates.get(step=Step.HOOK).output.get("hooks") or []
    winner = next((h for h in hooks if h.get("chosen")), concept.get("hook", {}))
    words = int(reel.target_seconds * WORDS_PER_SECOND)
    beats = "; ".join(f"{b['name']} ({b['purpose']})" for b in concept.get("beats", []))
    brief = "\n".join(
        [
            f"Storyboard a {reel.target_seconds}-second Instagram Reel, 2 to 8 scenes.",
            f"Concept: {concept.get('sentence', reel.prompt)}",
            f"Insight: {concept.get('insight', '')}",
            f"Planned beats: {beats}",
            f"Scene 1 is the hook. Its narration opens with \"{winner.get('spoken', '')}\""
            f" and its overlay is exactly \"{winner.get('overlay', '')}\".",
            f"Narration totals about {words} words (2.5 words a second).",
            "One scene is the turn and exactly one is the payoff. Each scene's seconds",
            "match its narration at 2.5 words a second." + _steer(reel, note),
        ]
    )

    def check(result: Board):
        try:
            spec = ReelSpec(
                slug=reel.slug,
                title=reel.title,
                kicker=kicker(reel.campaign),
                target_seconds=reel.target_seconds,
                scenes=[
                    SceneSpec(narration=s.narration, overlay=s.overlay, label=s.label)
                    for s in result.scenes
                ],
            )
        except SchemaError as exc:
            return None, [error["msg"] for error in exc.errors()]
        rows = [
            {
                "name": s.name,
                "purpose": s.purpose,
                "visual_beat": s.visual_beat,
                "seconds_est": s.seconds,
                "overlay": s.overlay.strip(),
                "narration": s.narration,
                "label": s.label,
            }
            for s in result.scenes
        ]
        problems = validate_beats(rows, spec)
        output = {
            "spec": spec.model_dump(),
            "scenes": rows,
            "seconds": round(sum(row["seconds_est"] for row in rows), 1),
            "words": sum(len(row["narration"].split()) for row in rows),
        }
        return output, problems

    output = _attempt(brief, Board, _skills(Step.BOARD), check)
    reel.spec = output.pop("spec")
    reel.save(update_fields=["spec", "updated_at"])
    return output


# -- the engine steps: plain data in, a record of what was made out ------------

MAX_PAUSE = 1.2  # seconds of silence a viewer reads as a stall
LOUDNESS = (-15.5, -12.5)  # LUFS around the -14 the mix aims for


def _spec(reel) -> ReelSpec:
    if not reel.spec:
        raise StepFailed("Board has no storyboard yet.")
    return ReelSpec.model_validate(reel.spec)


def look_step(reel, note: str = "") -> dict:
    from apps.image.services import generate

    spec = _spec(reel)
    rows = generate(reel.slug, spec.scenes, reel.store())
    if len(rows) != len(spec.scenes):
        raise StepFailed(f"{len(rows)} visuals for {len(spec.scenes)} scenes")
    return {"visuals": rows}


def voice_step(reel, note: str = "") -> dict:
    from apps.video.audio.services import run_voice

    result = run_voice(_spec(reel), reel.store())
    problems = []
    if result.max_silence > MAX_PAUSE:
        problems.append(f"a {result.max_silence:.1f} s pause is over the {MAX_PAUSE} s limit")
    if not LOUDNESS[0] <= result.loudness <= LOUDNESS[1]:
        problems.append(f"loudness {result.loudness:.1f} LUFS is outside -15.5 to -12.5")
    if problems:
        raise StepFailed("; ".join(problems))
    return result.model_dump()


def print_step(reel, note: str = "") -> dict:
    from apps.video.audio.cues import CueData
    from apps.video.services import run_compose, run_print

    spec = _spec(reel)
    voice = reel.gates.get(step=Step.VOICE).output
    look = reel.gates.get(step=Step.LOOK).output
    store = reel.store()
    visuals = {row["index"]: [row["key"]] for row in look.get("visuals", [])}
    keys = run_compose(
        spec,
        [CueData(**cue) for cue in voice["cues"]],
        voice["duration"],
        visuals,
        store,
    )
    # The composition points at the visuals and the voice; the encoder needs them.
    assets = [key for refs in visuals.values() for key in refs] + ["assets/voice.wav"]
    result = run_print(store, keys + assets, duration=voice["duration"])
    return {**result.model_dump(), "loudness": voice["loudness"], "cues": len(voice["cues"])}
