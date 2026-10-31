"""Timeline gate: the master is the clock."""

import shutil
import wave

import pytest

from apps.video.timeline import check_timeline, probe_duration

ffmpeg = pytest.mark.skipif(shutil.which("ffprobe") is None, reason="needs ffprobe")


def _wav(path, seconds, rate=48000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * seconds))


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    return root


def _cues(*spans):
    return [
        {"scene": index, "start": start, "end": end, "text": f"line {index}"}
        for index, (start, end) in enumerate(spans, start=1)
    ]


@ffmpeg
def test_missing_master_is_an_error(root):
    report = check_timeline(root, _cues((0.1, 1.0)))
    assert not report.ok
    assert "voice.wav" in report.errors[0]


@ffmpeg
def test_clean_timeline(root):
    _wav(root / "assets" / "voice.wav", 6.0)
    (root / "index.html").write_text('<div data-duration="6.0"></div>')
    report = check_timeline(root, _cues((0.1, 2.0), (2.4, 5.5)), duration=6.0)
    assert report.ok, report.errors
    assert report.duration == pytest.approx(6.0, abs=0.02)
    assert report.last_cue_end == pytest.approx(5.5)


@ffmpeg
def test_cue_past_master_fails(root):
    _wav(root / "assets" / "voice.wav", 2.0)
    report = check_timeline(root, _cues((0.1, 3.0)))
    assert not report.ok
    assert any("last cue" in error for error in report.errors)


@ffmpeg
def test_locked_duration_must_match(root):
    _wav(root / "assets" / "voice.wav", 4.0)
    report = check_timeline(root, _cues((0.1, 3.0)), duration=5.0)
    assert not report.ok
    assert any("locked duration" in error for error in report.errors)


@ffmpeg
def test_index_duration_must_match(root):
    _wav(root / "assets" / "voice.wav", 4.0)
    (root / "index.html").write_text('<div data-duration="9.0"></div>')
    report = check_timeline(root, _cues((0.1, 3.0)))
    assert not report.ok
    assert any("data-duration" in error for error in report.errors)


@ffmpeg
def test_cues_must_be_sane(root):
    _wav(root / "assets" / "voice.wav", 10.0)
    report = check_timeline(
        root,
        [
            {"scene": 1, "start": 2.0, "end": 1.0, "text": "backwards"},
            {"scene": 2, "start": 1.5, "end": 9.0, "text": ""},
        ],
    )
    assert not report.ok
    assert any("end" in error for error in report.errors)
    assert any("too long" in error for error in report.errors)
    assert any("empty" in error for error in report.errors)


@ffmpeg
def test_video_is_compared_to_master(root, tmp_path):
    _wav(root / "assets" / "voice.wav", 4.0)
    video = tmp_path / "clip.mp4"
    shutil.copyfile(root / "assets" / "voice.wav", video)
    report = check_timeline(root, _cues((0.1, 3.0)), video=video)
    assert not report.ok


@ffmpeg
def test_probe_duration(root):
    _wav(root / "assets" / "voice.wav", 1.5)
    assert probe_duration(root / "assets" / "voice.wav") == pytest.approx(1.5, abs=0.01)
