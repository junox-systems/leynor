"""Committed content specs. One JSON file per reel, no absolute paths."""

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


class SceneSpec(BaseModel):
    narration: str
    overlay: str
    label: str
    waveform: bool = False

    @field_validator("overlay")
    @classmethod
    def short_overlay(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("overlay is required")
        if len(value) > 44:
            raise ValueError("overlay over 44 characters will not fit")
        return value.strip()


class ReelSpec(BaseModel):
    slug: str
    title: str
    kicker: str = "THE FLYING EYES"
    voice: str = "fantine"
    tts_model: str = "english"
    sources: list[str] = Field(default_factory=list)
    pronounce: dict[str, str] = Field(default_factory=dict)
    target_seconds: int = 60
    scenes: list[SceneSpec]

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        if not SLUG.match(value):
            raise ValueError("slug is lowercase letters, digits and dashes")
        return value

    @field_validator("target_seconds")
    @classmethod
    def duration_window(cls, value: int) -> int:
        if not 60 <= value <= 180:
            raise ValueError("target_seconds must be 60-180")
        return value

    @field_validator("scenes")
    @classmethod
    def scene_count(cls, value: list[SceneSpec]) -> list[SceneSpec]:
        if not 2 <= len(value) <= 8:
            raise ValueError("a reel has 2 to 8 scenes")
        return value

    def sentences(self) -> list[tuple[int, str]]:
        """(scene index, sentence) pairs, in spoken order."""
        out = []
        for index, scene in enumerate(self.scenes, start=1):
            for sentence in SENTENCE.split(scene.narration.strip()):
                if sentence.strip():
                    out.append((index, sentence.strip()))
        return out

    def script(self) -> str:
        return "\n".join(scene.narration.strip() for scene in self.scenes)


def load_spec(path: Path | str) -> ReelSpec:
    return ReelSpec.model_validate(json.loads(Path(path).read_text()))
