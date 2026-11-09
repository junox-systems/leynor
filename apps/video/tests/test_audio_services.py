"""The voice step, with the model, the mixer and the aligner faked.

No torch, no whisper, no ffmpeg: the seam is the point.
"""

import json
import tempfile
import wave

import pytest

from apps.video.spec import ReelSpec
from django.core.files.storage import InMemoryStorage

from apps.runs.artifacts import ArtifactStore
from apps.video.audio.cues import VoiceResult
from apps.video.audio.mix import MixReport
from apps.video.audio.services import VoiceError, run_voice


class FakeTTS:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, output, voice):
        self.calls.append((text, voice))
        output.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(48000)
            handle.writeframes(b"\x00\x00" * 48000)


class FakeAligner:
    def __init__(self, cues):
        self.cues = cues
        self.coverage = 0.97
        self.backend = "fake"

    def align(self, wav, spec):
        class Result:
            pass

        result = Result()
        result.cues = self.cues
        result.coverage = self.coverage
        result.backend = self.backend
        return result


def fake_mixer(raw, out, scratch):
    out.write_bytes(raw.read_bytes())
    return MixReport(path=out, duration=2.0, loudness=-14.0, peak=-1.5, max_silence=0.2)


@pytest.fixture
def spec():
    return ReelSpec(
        slug="ep-voice",
        title="Voice",
        scenes=[
            {"narration": "One line.", "overlay": "One", "label": "a"},
            {"narration": "Two lines.", "overlay": "Two", "label": "b"},
        ],
    )


def cues():
    return [
        {"scene": 1, "start": 0.1, "end": 1.0, "text": "One line."},
        {"scene": 2, "start": 1.2, "end": 2.0, "text": "Two lines."},
    ]


def test_run_voice_writes_master_and_cue_map(tmp_path, spec):
    store = ArtifactStore(storage=InMemoryStorage())
    tts = FakeTTS()

    result = run_voice(
        spec,
        store,
        tts=tts,
        mixer=fake_mixer,
        aligner=FakeAligner(cues()),
    )

    assert isinstance(result, VoiceResult)
    assert store.get("assets/voice.wav")
    captions = json.loads(store.get("captions.json"))
    assert [cue["idx"] for cue in captions["cues"]] == [1, 2]
    assert captions["cues"][1]["text"] == "Two lines."
    assert tts.calls == [("One line. Two lines.", spec.voice)]


def test_run_voice_refuses_a_cue_count_mismatch(tmp_path, spec):
    with pytest.raises(VoiceError):
        run_voice(
            spec,
            ArtifactStore(storage=InMemoryStorage()),
            tts=FakeTTS(),
            mixer=fake_mixer,
            aligner=FakeAligner(cues()[:1]),
        )


def test_run_voice_removes_its_scratch(tmp_path, spec, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    store = ArtifactStore(storage=InMemoryStorage())
    run_voice(spec, store, tts=FakeTTS(), mixer=fake_mixer, aligner=FakeAligner(cues()))
    assert list(tmp_path.iterdir()) == []
