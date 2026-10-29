"""The master take: synthesize once, trim, normalize once, measure.

Nothing here touches the rendered video. Loudness and duration are settled
before composition, so a render is never re-encoded or trimmed afterwards.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from apps.voices.tts import PocketTTS

TARGET_I = -14.0
TARGET_TP = -1.5
LOUDNORM = f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA=11"
JSON_BLOCK = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.S)
SILENCE = re.compile(r"silence_duration:\s*([0-9.]+)")


class MixError(RuntimeError):
    pass


@dataclass
class MixReport:
    path: Path
    duration: float
    loudness: float
    peak: float
    max_silence: float


def _run(args: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise MixError(f"{args[0]} failed: {result.stderr.strip()[-400:]}")
    return result


def duration(path: Path) -> float:
    out = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    return float(out.stdout.strip())


def measure(path: Path) -> tuple[float, float]:
    out = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "ebur128=peak=true:framelog=quiet",
            "-f",
            "null",
            "-",
        ]
    )
    integrated = re.search(r"I:\s*(-?[0-9.]+) LUFS", out.stderr)
    peak = re.search(r"Peak:\s*(-?[0-9.]+) dBFS", out.stderr)
    return (
        float(integrated.group(1)) if integrated else 0.0,
        float(peak.group(1)) if peak else 0.0,
    )


def max_silence(path: Path, threshold: int = -40) -> float:
    out = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={threshold}dB:d=0.2",
            "-f",
            "null",
            "-",
        ]
    )
    found = [float(value) for value in SILENCE.findall(out.stderr)]
    return max(found) if found else 0.0


def synthesize_master(tts: PocketTTS, script: str, voice: str, raw: Path) -> Path:
    tts.synthesize(" ".join(script.split()), raw, voice)
    return raw


def mix(raw: Path, out: Path, scratch: Path) -> MixReport:
    trimmed = scratch / "voice.trim.wav"
    _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(raw),
            "-af",
            "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03,"
            "areverse,"
            "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03,"
            "areverse",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(trimmed),
        ]
    )
    probe = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(trimmed),
            "-af",
            f"{LOUDNORM}:print_format=json",
            "-f",
            "null",
            "-",
        ]
    )
    blocks = JSON_BLOCK.findall(probe.stderr)
    if not blocks:
        raise MixError("loudnorm returned no measurement")
    stats = json.loads(blocks[-1])
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(trimmed),
            "-af",
            f"{LOUDNORM}:measured_I={stats['input_i']}:"
            f"measured_TP={stats['input_tp']}:measured_LRA={stats['input_lra']}:"
            f"measured_thresh={stats['input_thresh']}:offset={stats['target_offset']}:"
            "linear=true",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(out),
        ]
    )
    loudness, peak = measure(out)
    return MixReport(
        path=out,
        duration=round(duration(out), 3),
        loudness=loudness,
        peak=peak,
        max_silence=round(max_silence(out), 3),
    )
