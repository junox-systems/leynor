"""The step to skill map points at real files."""

from reel_playbook.skills import missing, read, skill_paths
from reel_playbook.steps import STEPS


def test_every_step_has_a_must_read_skill():
    for step in STEPS:
        assert step.skills, step.id


def test_every_skill_path_exists():
    for step in STEPS:
        assert missing(step) == [], step.id
        assert missing(step, optional=True) == [], step.id


def test_must_and_optional_are_separate():
    for step in STEPS:
        must = {str(path) for path in skill_paths(step)}
        optional = {str(path) for path in skill_paths(step, optional=True)}
        assert not must & optional, step.id


def test_read_returns_the_procedure_text():
    idea = next(step for step in STEPS if step.id == "idea")
    text = read(idea, optional=True)
    assert "creative-director" in text
    assert "insight" in text.lower()


def test_look_reads_the_composition_contract():
    look = next(step for step in STEPS if step.id == "look")
    text = read(look)
    assert "sub-compositions" in text
    assert "data-composition-id" in text
