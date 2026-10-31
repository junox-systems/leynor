"""Skill paths resolve against the repo's skills directory."""

from apps.text.skills import missing, read, skill_paths

NAMES = ["creative-director/SKILL.md", "video-script/SKILL.md"]


def test_known_skills_exist():
    assert missing(NAMES) == []
    assert all(path.exists() for path in skill_paths(NAMES))


def test_unknown_skills_are_reported():
    assert missing(["nope/SKILL.md"]) == [str(skill_paths(["nope/SKILL.md"])[0])]


def test_read_returns_the_procedure_text():
    text = read(NAMES)
    assert "creative-director" in text
    assert "insight" in text.lower()


def test_read_skips_missing_files():
    assert read(["nope/SKILL.md"]) == ""
