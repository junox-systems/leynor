"""Alignment: turn a master take into cues.

We know the words, so ASR only supplies timings. Whisper output is corrected
against the script with a sequence match; unmatched script words are
interpolated. One pass per master, cached by the caller.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .content import ReelSpec

VERSION = "1.0.0"
TOKEN = re.compile(r"[a-z0-9']+")


class AlignError(RuntimeError):
    pass


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class AlignResult:
    cues: list[dict]
    words: list[Word]
    coverage: float
    backend: str = "faster_whisper"


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def _interpolate(known: list[Word | None], starts: list[float]) -> list[Word]:
    out: list[Word] = []
    last_end = starts[0] if starts else 0.0
    pending: list[int] = []

    def flush(upto: float) -> None:
        nonlocal last_end
        if not pending:
            return
        count = len(pending)
        span = max(0.01, upto - last_end)
        for position, index in enumerate(pending):
            begin = last_end + span * position / count
            end = last_end + span * (position + 1) / count
            word = known[index]
            out[index] = Word(word.text if word else "", begin, end)
        last_end = upto
        pending.clear()

    for index, word in enumerate(known):
        if word is None:
            pending.append(index)
            out.append(Word("", 0.0, 0.0))
            continue
        if pending:
            flush(word.start)
        out.append(Word(word.text, word.start, word.end))
        last_end = word.end
    if pending:
        flush(last_end + 0.2 * len(pending))
    return out


def map_words(script: list[str], heard: list[Word]) -> tuple[list[Word], float]:
    """Timing for every script token, using the heard words as evidence."""
    heard_tokens = [tokens(word.text) for word in heard]
    flat_heard: list[str] = []
    flat_words: list[Word] = []
    for word, parts in zip(heard, heard_tokens):
        for part in parts or [word.text]:
            flat_heard.append(part)
            flat_words.append(word)

    matcher = SequenceMatcher(None, script, flat_heard, autojunk=False)
    known: list[Word | None] = [None] * len(script)
    matched = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag not in ("equal", "replace"):
            continue
        span = flat_words[j1:j2]
        if not span:
            continue
        for offset, index in enumerate(range(i1, i2)):
            count = i2 - i1
            if len(span) == count:
                word = span[offset]
                known[index] = Word(script[index], word.start, word.end)
            else:
                ratio = offset / max(count - 1, 1)
                word = span[min(int(ratio * (len(span) - 1)), len(span) - 1)]
                known[index] = Word(script[index], word.start, word.end)
            if tag == "equal":
                matched += 1

    starts = [word.start for word in flat_words] or [0.0]
    filled = _interpolate(known, starts)
    for index, word in enumerate(filled):
        word.text = script[index]
    coverage = matched / max(len(script), 1)
    return filled, coverage


def sentence_spans(spec: ReelSpec) -> list[tuple[int, str, int, int]]:
    """(scene, sentence, first token, last token + 1)."""
    spans, cursor = [], 0
    for scene, sentence in spec.sentences():
        count = len(tokens(sentence))
        spans.append((scene, sentence, cursor, cursor + count))
        cursor += count
    return spans


def cues_from_words(
    spec: ReelSpec,
    words: list[Word],
    lead: float = 0.12,
    tail: float = 0.35,
    duration: float | None = None,
) -> list[dict]:
    cues: list[dict] = []
    previous_end = 0.0
    for scene, sentence, first, last in sentence_spans(spec):
        chunk = words[first:last]
        if not chunk:
            continue
        start = max(0.0, chunk[0].start - lead, previous_end)
        end = max(start + 0.2, chunk[-1].end + tail)
        if duration is not None:
            end = min(end, duration)
            start = min(start, max(0.0, end - 0.2))
        cues.append(
            {
                "scene": scene,
                "start": round(start, 3),
                "end": round(end, 3),
                "text": sentence,
            }
        )
        previous_end = end
    return cues


def _pcm16k(wav: Path):
    """Mono 16 kHz float32 samples. PyAV's API drifts; ffmpeg does not."""
    import numpy as np

    try:
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000",
             "-f", "s16le", "-"],
            capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AlignError(f"cannot decode {wav}: {exc}") from exc
    audio = np.frombuffer(out.stdout, dtype=np.int16)
    if not audio.size:
        raise AlignError(f"no audio in {wav}")
    return audio.astype(np.float32) / 32768.0


class FasterWhisper:
    name = "faster_whisper"
    version = VERSION
    def __init__(self, size: str = "base.en", threads: int = 4):
        self.size = size
        self.threads = threads
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:  # pragma: no cover - dependency is base
                raise AlignError("faster-whisper is not installed; uv sync") from exc
            self._model = WhisperModel(
                self.size, device="cpu", compute_type="int8", cpu_threads=self.threads
            )
        return self._model

    def words(self, wav: Path) -> list[Word]:
        model = self._load()
        segments, _ = model.transcribe(
            _pcm16k(wav),
            language="en",
            beam_size=1,
            word_timestamps=True,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        out = []
        for segment in segments:
            for word in segment.words or []:
                out.append(Word(word.word.strip(), float(word.start), float(word.end)))
        return out

    def align(self, wav: Path, spec: ReelSpec) -> AlignResult:
        heard = self.words(wav)
        if not heard:
            raise AlignError(f"no speech found in {wav}")
        words, coverage = map_words(tokens(spec.script()), heard)
        from .voice import duration as wav_duration

        return AlignResult(
            cues=cues_from_words(spec, words, duration=wav_duration(wav)),
            words=words,
            coverage=round(coverage, 3),
            backend=self.name,
        )


def write_cues(path: Path, cues: list[dict]) -> None:
    path.write_text(json.dumps({"cues": cues}, indent=2) + "\n")
