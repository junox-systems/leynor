"""Step catalogue: every step, with the name a person reads."""

from pydantic import BaseModel

from apps.projects.gates import Step


class StepSpec(BaseModel):
    id: Step
    index: int
    name: str
    description: str
    inputs: list[str]
    outputs: list[str]
    gate: str
    owner: str
    artifacts: list[str] = []
    skills: list[str] = []
    optional_skills: list[str] = []
    llm: bool = False
    prompt: str | None = None


STEPS: tuple[StepSpec, ...] = (
    StepSpec(
        id=Step.IDEA,
        skills=[
            "creative-director/SKILL.md",
            "creative-director/references/insight-mining.md",
            "creative-director/references/scoring-calibration.md",
            "creative-director/references/methods-catalog.md",
        ],
        optional_skills=[
            "viral-short-form-ideas/SKILL.md",
            "ig-audience-insights/SKILL.md",
        ],
        index=1,
        name="Spark",
        description=(
            "Find the one true thing worth saying, and the evidence it is true. "
            "A Reel is execution-level: days, not campaigns."
        ),
        inputs=["niche", "the person", "primary goal", "one cited input"],
        outputs=["idea sentence", "insight sentence", "primary goal"],
        gate="one sentence, HumanKind >= 7, a cited input, adversarial pass answered",
        owner="creative-director (phases 1-4)",
        llm=True,
        prompt=(
            "You are the idea stage of a short vertical video. Produce one idea sentence "
            "and one insight sentence in the form 'audience wants X, but Y stands in the "
            "way, because Z'. Execution-level only. Name the primary goal as saves, "
            "shares or follows and say which payoff the hook will promise. No idea "
            "without an insight."
        ),
    ),
    StepSpec(
        id=Step.HOOK,
        skills=["viral-hooks/SKILL.md", "viral-instagram-reels/SKILL.md"],
        optional_skills=["ig-hook-extractor/SKILL.md"],
        index=2,
        name="First Three Seconds",
        description=(
            "Earn the next ten seconds before the viewer decides. The hook must preview "
            "the payoff one specific person would send to a friend."
        ),
        inputs=["idea sentence", "insight sentence", "primary goal"],
        outputs=[
            "6-10 labelled hooks",
            "winner with verbal line, first frame, overlay",
        ],
        gate="hook checklist passed, overlay readable muted, adversarial pass answered",
        owner="viral-hooks + viral-instagram-reels (reels-hook)",
        llm=True,
        prompt=(
            "You write hooks for a vertical video. Produce six to ten hooks across at "
            "least three archetypes. Each hook has three layers: the spoken line, what "
            "is on screen in frame one, and the overlay text in three to seven words. "
            "Then pick one winner and state the objection against it and why it survives."
        ),
    ),
    StepSpec(
        id=Step.BOARD,
        skills=[
            "video-script/SKILL.md",
            "hyperframes-creative/SKILL.md",
            "hyperframes-creative/references/story-spine.md",
            "hyperframes-creative/references/beat-direction.md",
            "hyperframes-creative/references/narration.md",
        ],
        optional_skills=[
            "viral-short-form/SKILL.md",
            "hyperframes-creative/references/storyboard-recipe.md",
        ],
        index=3,
        name="Storyboard",
        description=(
            "Turn the hook into scenes with a line, an overlay, a visual beat and an "
            "estimated length. The voice replaces the estimate with real cues later."
        ),
        inputs=["winning hook", "goal", "spoken-word budget"],
        outputs=["STORYBOARD.md", "boards/storyboard.html"],
        gate="person approves the board; every scene has a visual beat",
        owner="viral-instagram-reels + video-script + hyperframes (storyboard format)",
        artifacts=["STORYBOARD.md", "boards/storyboard.html"],
    ),
    StepSpec(
        id=Step.LOOK,
        skills=[
            "hyperframes-core/SKILL.md",
            "hyperframes-core/references/sub-compositions.md",
            "hyperframes-core/references/tracks-and-clips.md",
            "hyperframes-core/references/determinism-rules.md",
            "hyperframes-creative/references/video-composition.md",
            "hyperframes-creative/references/typography.md",
            "hyperframes-creative/references/house-style.md",
        ],
        optional_skills=[
            "hyperframes-registry/SKILL.md",
            "hyperframes-keyframes/SKILL.md",
            "image-visual-skills/SKILL.md",
        ],
        index=4,
        name="Look",
        description=(
            "Visuals before voice. Every scene resolves through ImageTools to a frozen "
            "local asset with a tool, version and seed on record."
        ),
        inputs=["storyboard", "tone", "palette"],
        outputs=["frame.md", "assets/visuals/*", "assets/CREDITS.md"],
        gate="every scene has a visual, credits complete, 9:16 legibility holds",
        owner="hyperframes-creative + ImageTools (A / A+)",
        artifacts=["frame.md", "assets/visuals/*", "assets/CREDITS.md"],
    ),
    StepSpec(
        id=Step.VOICE,
        skills=[
            "hyperframes-creative/references/narration.md",
            "video-script/SKILL.md",
        ],
        optional_skills=["hyperframes-animation/SKILL.md"],
        index=5,
        name="Voice",
        description=(
            "One continuous take per episode. TTS once, align to the known script, trim, "
            "normalize once. Cues become the clock for every scene."
        ),
        inputs=["script", "voice and tts_model", "pronounce map"],
        outputs=["assets/voice.wav", "captions.json"],
        gate="cue drift <= 80 ms, max pause <= 1.2 s, loudness in range, person listened",
        owner="Pocket TTS 100M + faster-whisper",
        artifacts=["assets/voice.wav", "captions.json"],
    ),
    StepSpec(
        id=Step.PRINT,
        skills=["hyperframes-cli/SKILL.md", "hyperframes-core/SKILL.md"],
        optional_skills=[
            "hyperframes-animation/SKILL.md",
            "hyperframes-registry/SKILL.md",
        ],
        index=6,
        name="Print",
        description=(
            "Compose from the visuals, lay the master under it once, render, and prove "
            "duration, loudness, captions and pixels."
        ),
        inputs=["visuals", "cue map", "master", "composition"],
        outputs=["index.html", "compositions/*", "out.mp4"],
        gate="check 0 errors, duration, captions on cue, frames inspected, person approves",
        owner="HyperFrames + hyperframes-cli",
        artifacts=["index.html", "compositions/*", "out.mp4"],
    ),
)

BY_ID = {step.id: step for step in STEPS}


def resolve(step: str | Step) -> StepSpec:
    if isinstance(step, Step):
        return BY_ID[step]
    try:
        return BY_ID[Step(step.strip().lower())]
    except ValueError:
        raise KeyError(
            f"unknown step {step!r}; one of {', '.join(s.value for s in Step)}"
        ) from None
