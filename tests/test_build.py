"""Legacy import and the pipeline helpers that do not need a voice model."""

from reel_playbook.build import _legacy_cues


def test_legacy_cues_from_storyboard(tmp_path):
    (tmp_path / "STORYBOARD.md").write_text(
        "# STORYBOARD\n\n"
        "## Frame 1: Hook (0-7.133 s)\n"
        "- narration: First line.\n"
        "- on-screen: Hook\n\n"
        "## Frame 2: Fact (7.133-13.467 s)\n"
        "- narration: Second line.\n"
    )
    cues = _legacy_cues(tmp_path)
    assert [cue["scene"] for cue in cues] == [1, 2]
    assert cues[0] == {"scene": 1, "start": 0.0, "end": 7.133, "text": "First line."}
    assert cues[1]["start"] == 7.133


def test_legacy_cues_without_storyboard(tmp_path):
    assert _legacy_cues(tmp_path) == []
