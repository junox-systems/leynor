"""Pocket TTS, 100M weights, in-process.

The model id is the value the library takes for ``language``: ``english`` is the
100M model, ``english_18m_2026-10`` and friends are the fast, flatter ones.

Installed by ``uv sync``. Torch comes from the CPU index configured
in ``pyproject.toml``; the model is loaded once per process and reused for every
scene, which is why this is a class and not a subprocess call.
"""

import importlib.util
import subprocess
import wave
from pathlib import Path

POCKET_TTS_100M = "english"
DEFAULT_VOICE = "fantine"


class TTSError(RuntimeError):
    pass


class PocketTTS:
    """Lazy in-process Pocket TTS. 100M by default, one model per instance."""

    def __init__(self, model: str = POCKET_TTS_100M):
        self.model = model
        self._tts = None
        self._voices: dict[str, object] = {}

    @staticmethod
    def installed() -> bool:
        return importlib.util.find_spec("pocket_tts") is not None

    def load(self):
        if self._tts is None:
            if not self.installed():
                raise TTSError(
                    "pocket-tts is not installed; run `uv sync`"
                )
            from pocket_tts import TTSModel

            self._tts = TTSModel.load_model(language=self.model)
        return self._tts

    def voice_state(self, voice: str):
        if voice not in self._voices:
            self.load()
            self._voices[voice] = self._tts.get_state_for_audio_prompt(voice)
        return self._voices[voice]

    def synthesize(self, text: str, output: Path, voice: str = DEFAULT_VOICE) -> Path:
        if not text.strip():
            raise TTSError("nothing to say")
        state = self.voice_state(voice)
        audio = self._tts.generate_audio(state, text)
        self._write(output, audio, self._tts.sample_rate)
        return output

    @staticmethod
    def _write(output: Path, audio, sample_rate: int) -> None:
        import torch

        samples = audio.detach().to(torch.float32).clamp(-1, 1)
        pcm = (samples * 32767).to(torch.int16).reshape(-1).cpu().numpy().tobytes()
        output.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm)

    @staticmethod
    def duration(path: Path) -> float | None:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        try:
            return float(out.stdout.strip())
        except ValueError:
            return None
