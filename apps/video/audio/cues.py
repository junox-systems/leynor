"""Cue map: the value objects the renderer reads, and the voice step's result.

Rows live in `apps.video.audio.models.Cue`. These pydantic models are what crosses
the app boundary, so `renders` never needs the voices tables.
"""

from pydantic import BaseModel, Field


class CueData(BaseModel):
    idx: int
    scene: int
    start: float
    end: float
    text: str


class VoiceResult(BaseModel):
    duration: float
    loudness: float
    peak: float
    max_silence: float
    cues: list[CueData] = Field(default_factory=list)
    coverage: float = 0.0
    backend: str = ""
