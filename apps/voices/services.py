"""One master take: synthesize, mix, align, write the cue map. No ORM."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from apps.projects.spec import ReelSpec
from apps.voices.cues import CueData, VoiceResult
from apps.voices.mix import MixReport, mix, synthesize_master
from apps.voices.tts import PocketTTS


class VoiceError(RuntimeError):
    pass


class Aligner(Protocol):
    def align(self, wav: Path, spec: ReelSpec): ...


def run_voice(
    spec: ReelSpec,
    store,
    *,
    tts: PocketTTS | None = None,
    mixer: Callable[[Path, Path, Path], MixReport] = mix,
    aligner: Aligner | None = None,
    whisper_size: str = "base.en",
    threads: int = 4,
) -> VoiceResult:
    if aligner is None:
        from apps.voices.asr import FasterWhisper

        aligner = FasterWhisper(size=whisper_size, threads=threads)
    tts = tts or PocketTTS(model=spec.tts_model)

    with store.tmpdir() as scratch:
        raw = scratch / "master.raw.wav"
        master = scratch / "voice.wav"
        synthesize_master(tts, spec.script(), spec.voice, raw)
        report = mixer(raw, master, scratch)

        result = aligner.align(master, spec)
        expected = len(spec.sentences())
        if len(result.cues) != expected:
            raise VoiceError(
                f"aligner returned {len(result.cues)} cues, expected {expected}"
            )

        store.put("assets/voice.wav", master.read_bytes())
        cues = [
            CueData(
                idx=index,
                scene=int(cue["scene"]),
                start=float(cue["start"]),
                end=float(cue["end"]),
                text=str(cue["text"]),
            )
            for index, cue in enumerate(result.cues, start=1)
        ]
        store.put(
            "captions.json",
            json.dumps({"cues": [cue.model_dump() for cue in cues]}, indent=2) + "\n",
        )

    return VoiceResult(
        duration=report.duration,
        loudness=report.loudness,
        peak=report.peak,
        max_silence=report.max_silence,
        cues=cues,
        coverage=result.coverage,
        backend=result.backend,
    )
