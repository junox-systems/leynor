"""Creative gates: records must prove quality before the state machine moves."""

import pytest

from reel_playbook.book import ReelPlaybook, StateError
from reel_playbook.build import build
from reel_playbook.content import ReelSpec
from reel_playbook.creative import validate_beats, validate_hooks, validate_idea
from reel_playbook.design import default_frame, parse_frame
from reel_playbook.storage import Workspace


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
        "adversarial": {"objection": "runtime is trivia", "answer": "length promises payoff"},
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


@pytest.fixture
def spec():
    return ReelSpec(
        slug="ep-creative",
        title="Creative",
        scenes=[
            {"narration": "One line here.", "overlay": "One line", "label": "a"},
            {"narration": "Two lines here now.", "overlay": "Two lines", "label": "b"},
            {"narration": "Three lines here now.", "overlay": "Three lines", "label": "c"},
            {"narration": "Four lines here now.", "overlay": "Four lines", "label": "d"},
            {"narration": "Five lines here now.", "overlay": "Five lines", "label": "e"},
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
            "seconds_est": len(scene.narration.split()) / 2.5,
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


def test_frame_roundtrip_and_defaults():
    design = parse_frame(default_frame())
    assert design.accent == "#e0a33e"
    assert design.caption_bottom == "30%"
    assert parse_frame(None).caption_bottom == "30%"
    custom = parse_frame('---\npalette_accent: "#ff0000"\ncaption_bottom: "22%"\n---\n')
    assert custom.accent == "#ff0000"
    assert custom.caption_bottom == "22%"


def test_build_refuses_without_idea(tmp_path):
    ws = Workspace(tmp_path / "ws")
    book = ReelPlaybook.create(ws, "ep-no-idea")
    book.put_text(
        "spec.json",
        '{"slug":"ep-no-idea","title":"T","scenes":['
        '{"narration":"One.","overlay":"One","label":"a"},'
        '{"narration":"Two.","overlay":"Two","label":"b"}]}',
        kind="spec",
    )
    with pytest.raises(Exception) as error:
        build(ws, "ep-no-idea", render=False)
    assert "idea gate" in str(error.value)
