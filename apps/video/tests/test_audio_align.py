"""Alignment: known script, ASR timings, no invented words."""

from apps.video.audio.asr import Word, cues_from_words, map_words, tokens
from apps.video.spec import ReelSpec


def test_tokens_are_lowercase_words():
    assert tokens("Lay with Me, 2009!") == ["lay", "with", "me", "2009"]


def test_map_words_keeps_script_text_and_heard_time():
    script = ["lay", "with", "me"]
    heard = [
        Word("Lay", 0.1, 0.3),
        Word("with", 0.35, 0.5),
        Word("me", 0.55, 0.8),
    ]
    words, coverage = map_words(script, heard)
    assert [word.text for word in words] == script
    assert words[0].start == 0.1
    assert words[-1].end == 0.8
    assert coverage == 1.0


def test_map_words_substitutes_misheard_words():
    script = ["two", "thousand", "nine"]
    heard = [
        Word("to", 0.0, 0.2),
        Word("thousand", 0.25, 0.6),
        Word("nine", 0.65, 0.9),
    ]
    words, coverage = map_words(script, heard)
    assert [word.text for word in words] == script
    assert words[0].start == 0.0
    assert coverage < 1.0


def test_map_words_interpolates_missing_words():
    script = ["a", "b", "c"]
    heard = [Word("a", 0.0, 0.5), Word("c", 1.0, 1.5)]
    words, coverage = map_words(script, heard)
    assert [word.text for word in words] == script
    assert 0.5 <= words[1].start <= 1.0
    assert words[1].end >= words[1].start
    assert coverage == 2 / 3


def _spec() -> ReelSpec:
    return ReelSpec(
        slug="ep-01",
        title="Ep 01",
        scenes=[
            {"narration": "One line. Two lines.", "overlay": "One", "label": "a"},
            {"narration": "Three lines.", "overlay": "Three", "label": "b"},
        ],
    )


def test_cues_cover_every_sentence_in_order():
    spec = _spec()
    words = [
        Word("one", 0.2, 0.4),
        Word("line", 0.45, 0.7),
        Word("two", 0.8, 1.0),
        Word("lines", 1.05, 1.3),
        Word("three", 1.5, 1.8),
        Word("lines", 1.85, 2.1),
    ]
    cues = cues_from_words(spec, words)
    assert [cue["scene"] for cue in cues] == [1, 1, 2]
    starts = [cue["start"] for cue in cues]
    assert starts == sorted(starts)
    assert all(cue["end"] > cue["start"] for cue in cues)
    assert cues[0]["text"] == "One line."


def test_cues_are_bounded_by_the_master():
    spec = _spec()
    words = [Word("one", 0.2, 0.4)] + [
        Word("w", 0.5 + i * 0.1, 0.55 + i * 0.1) for i in range(5)
    ]
    cues = cues_from_words(spec, words)
    assert cues[-1]["end"] <= words[-1].end + 0.35 + 1e-9


def test_cues_never_overlap():
    spec = ReelSpec(
        slug="ep-02",
        title="Ep 02",
        scenes=[
            {"narration": "One. Two.", "overlay": "One", "label": "a"},
            {"narration": "Three.", "overlay": "Three", "label": "b"},
        ],
    )
    words = [
        Word("one", 0.0, 0.4),
        Word("two", 0.45, 0.7),
        Word("three", 0.75, 1.0),
    ]
    cues = cues_from_words(spec, words)
    assert cues[0]["end"] <= cues[1]["start"]
    assert cues[1]["end"] <= cues[2]["start"]


def test_cues_are_clamped_to_the_master():
    spec = _spec()
    words = [
        Word("one", 0.2, 0.4),
        Word("line", 0.45, 0.7),
        Word("two", 0.8, 1.0),
        Word("lines", 1.05, 1.3),
        Word("three", 1.5, 1.8),
        Word("lines", 1.85, 2.1),
    ]
    cues = cues_from_words(spec, words, duration=2.0)
    assert max(cue["end"] for cue in cues) <= 2.0
