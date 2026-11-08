"""Model output that passes the real validators, for tests that fake the text engine."""

from unittest import mock

from apps.instagram import services

WORDS_32 = " ".join(["word"] * 31) + " end."


def concept(n: int, *, source: str = "idea") -> services.Concept:
    return services.Concept(
        title=f"Take number {n}",
        sentence=f"Day three is where habits die, and take {n} shows the fix.",
        insight=(
            "A beginner wants a habit that sticks, but motivation fades by day three, "
            "because nobody plans for the dip."
        ),
        score=8,
        citations=[services.Citation(claim="habits fade by day three", source=source)],
        hook=services.Hook(
            archetype="contrarian",
            spoken=f"Motivation is a trap, take {n}.",
            first_frame="A calendar with day three circled",
            overlay="Motivation is a trap",
        ),
        beats=[
            services.Beat(name="The trap", purpose="hook", seconds=6),
            services.Beat(name="The dip", purpose="turn", seconds=30),
            services.Beat(name="The fix", purpose="payoff", seconds=24),
        ],
        objection="Everyone says this already.",
        answer="Nobody names day three.",
    )


def hooks() -> services.HookSet:
    archetypes = ["number-first", "relatable", "myth-buster", "confession", "listicle", "how-i"]
    return services.HookSet(
        hooks=[
            services.Hook(
                archetype=archetype,
                spoken=f"Alternate {archetype}.",
                first_frame="A frame",
                overlay="Three words here",
            )
            for archetype in archetypes
        ]
    )


def board(first_overlay: str = "Motivation is a trap") -> services.Board:
    purposes = ["hook", "setup", "turn", "payoff"]
    return services.Board(
        scenes=[
            services.BoardScene(
                name=f"Scene {n}",
                purpose=purpose,
                narration=WORDS_32,
                overlay=first_overlay if n == 1 else f"Overlay {n}",
                label=f"label {n}",
                visual_beat="Something moves",
                seconds=15,
            )
            for n, purpose in enumerate(purposes, start=1)
        ]
    )


class FakeText:
    """Stands in for `text.services.structured`, answering by schema."""

    def __init__(self, *, concepts=None, fail_on=None):
        self.concepts = concepts or [concept(1), concept(2), concept(3)]
        self.fail_on = fail_on
        self.briefs = []

    def __call__(self, brief, *, output_type, instructions=""):
        self.briefs.append((output_type.__name__, brief))
        if output_type is self.fail_on:
            raise RuntimeError("model unavailable")
        if output_type is services.ConceptSet:
            return services.ConceptSet(concepts=self.concepts)
        if output_type is services.HookSet:
            return hooks()
        if output_type is services.Board:
            return board()
        raise AssertionError(output_type)

    def patch(self):
        return mock.patch.object(services, "structured", self)


def fake_voice(reel, note=""):
    return {
        "duration": 61.0,
        "loudness": -14.0,
        "peak": -1.6,
        "max_silence": 0.4,
        "cues": [],
        "coverage": 1.0,
        "backend": "fake",
    }


def fake_print(reel, note=""):
    reel.store().put("out.mp4", b"\x00\x00\x00\x18ftypmp42" + b"0" * 64)
    return {"path": "out.mp4", "sha256": "x", "duration": 61.0, "fps": 30.0, "loudness": -14.0, "cues": 0}


def engines():
    """Fake the heavy engines; Look stays real (procedural, local, fast)."""
    return (
        mock.patch.object(services, "voice_step", fake_voice),
        mock.patch.object(services, "print_step", fake_print),
    )
