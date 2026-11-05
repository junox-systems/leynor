"""Creative gates: records must prove quality before the state machine moves."""

import pytest

from apps.instagram.validators import validate_beats, validate_hooks, validate_idea
from apps.video.spec import ReelSpec


def idea(**overrides):
    base = {
        "sentence": "A long debut is an argument about what the band values.",
        "insight": "The audience wants a statement, but debuts are cut short, because radio rewards brevity.",
        "goal": "saves",
        "score": 8.0,
        "citations": [{"claim": "runtime is 5:47", "source": "track credits"}],
        "alternatives": [
            {"title": "comparison", "rejected": "dates the band"},
            {"title": "release history", "rejected": "repeats reel 01"},
        ],
        "adversarial": {
            "objection": "runtime is trivia",
            "answer": "length promises payoff",
        },
    }
    base.update(overrides)
    return base


def hooks(count=6, archetypes=("number-first", "contrarian", "framework")):
    rows = []
    for index in range(count):
        rows.append(
            {
                "archetype": archetypes[index % len(archetypes)],
                "spoken": f"spoken {index}",
                "first_frame": f"frame {index}",
                "overlay": f"Three word hook {index}",
                "chosen": index == 0,
                "objection": "objection" if index == 0 else None,
                "answer": "answer" if index == 0 else None,
            }
        )
    return rows


LINE = " ".join(["word"] * 30)


@pytest.fixture
def spec():
    return ReelSpec(
        slug="ep-creative",
        title="Creative",
        target_seconds=60,
        scenes=[
            {"narration": LINE, "overlay": "One line", "label": "a"},
            {"narration": LINE, "overlay": "Two lines", "label": "b"},
            {"narration": LINE, "overlay": "Three lines", "label": "c"},
            {"narration": LINE, "overlay": "Four lines", "label": "d"},
            {"narration": LINE, "overlay": "Five lines", "label": "e"},
        ],
    )


def beats(spec):
    purposes = ["hook", "build", "turn", "evidence", "payoff"]
    return [
        {
            "name": f"beat {index + 1}",
            "purpose": purposes[index],
            "overlay": scene.overlay,
            "visual_beat": "plate and rule",
            "seconds_est": round(len(scene.narration.split()) / 2.5, 2),
        }
        for index, scene in enumerate(spec.scenes)
    ]


def test_idea_accepts_a_scored_concept():
    assert validate_idea(idea()) == []


def test_idea_requires_missing_record():
    assert validate_idea(None)


def test_idea_rejects_low_score_and_missing_evidence():
    problems = validate_idea(
        idea(score=6.0, citations=[], adversarial={}, alternatives=[])
    )
    assert any("below the gate" in problem for problem in problems)
    assert any("citation" in problem for problem in problems)
    assert any("objection" in problem for problem in problems)
    assert any("rejected concepts" in problem for problem in problems)


def test_idea_rejects_a_sentence_without_insight_shape():
    problems = validate_idea(idea(insight="people like long songs"))
    assert any("wants" in problem for problem in problems)
    assert any("because" in problem for problem in problems)


def test_hooks_accept_a_screened_set():
    assert validate_hooks(hooks()) == []


def test_hooks_reject_too_few_or_one_archetype():
    assert validate_hooks(hooks(count=5))
    assert validate_hooks(hooks(archetypes=("contrarian",)))


def test_hooks_reject_wrong_choice_count_and_bad_overlay():
    rows = hooks()
    rows[1]["chosen"] = True
    assert any("exactly one hook" in problem for problem in validate_hooks(rows))
    rows = hooks()
    rows[2]["overlay"] = "one two three four five six seven eight"
    assert any("3-7" in problem for problem in validate_hooks(rows))


def test_beats_accept_a_planned_arc(spec):
    assert validate_beats(beats(spec), spec) == []


def test_beats_require_turn_payoff_and_matching_overlays(spec):
    rows = beats(spec)
    rows[2]["purpose"] = "build"
    rows[4]["overlay"] = "drifted"
    problems = validate_beats(rows, spec)
    assert any("turn" in problem for problem in problems)
    assert any("does not match" in problem for problem in problems)


def test_beats_must_match_scene_count(spec):
    assert validate_beats(beats(spec)[:-1], spec)


def test_target_must_be_60_to_180():
    from pydantic import ValidationError

    for value in (30, 181):
        with pytest.raises(ValidationError):
            ReelSpec(
                slug="ep-target",
                title="T",
                target_seconds=value,
                scenes=[
                    {"narration": "a b c.", "overlay": "a b c", "label": "a"},
                    {"narration": "d e f.", "overlay": "d e f", "label": "b"},
                ],
            )


def test_beats_must_reach_the_target(spec):
    rows = beats(spec)
    for row in rows:
        row["seconds_est"] = 2.0
    problems = validate_beats(rows, spec)
    assert any("target" in problem for problem in problems)


def test_short_script_fails_the_target(spec):
    short = ReelSpec(
        slug="ep-short",
        title="Short",
        target_seconds=60,
        scenes=[
            {"narration": "one two.", "overlay": "one two", "label": "a"},
            {"narration": "three four.", "overlay": "three four", "label": "b"},
        ],
    )
    rows = [
        {
            "name": "a",
            "purpose": "hook",
            "overlay": "one two",
            "visual_beat": "plate",
            "seconds_est": 30.0,
        },
        {
            "name": "b",
            "purpose": "payoff",
            "overlay": "three four",
            "visual_beat": "plate",
            "seconds_est": 30.0,
        },
    ]
    problems = validate_beats(rows, short)
    assert any("words is short" in problem for problem in problems)
