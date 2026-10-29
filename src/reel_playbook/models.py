"""Pydantic models for records, views and reports."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .steps import StateId, StepId

VERSION = "0.1.0"

Action = Literal["init", "pass", "fail", "rewind", "set", "tts", "align", "timeline",
                 "draft", "build"]
StepStatusKind = Literal["done", "current", "failed", "locked"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tokens(BaseModel):
    model_config = ConfigDict(extra="allow")

    fps: int = 30
    width: int = 1080
    height: int = 1920
    tolerance_frames: int = 1
    language: str = "english"
    duration: float | None = None
    voice: str | None = None
    tts_model: str = "english"

    def get(self, key: str) -> Any:
        return getattr(self, key, None)

    def set(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def public(self) -> dict[str, Any]:
        return self.model_dump()


class GateRecord(BaseModel):
    step: StepId
    result: Literal["pass", "fail"] | None = None
    attempts: int = 0
    evidence: str | None = None
    reason: str | None = None
    at: datetime | None = None


class LogEntry(BaseModel):
    at: datetime
    action: Action
    from_state: StateId
    to_state: StateId
    note: str | None = None


class Cue(BaseModel):
    scene: int
    start: float
    end: float
    text: str


class StepStatus(BaseModel):
    id: StepId
    index: int
    name: str
    description: str
    status: StepStatusKind
    attempts: int = 0
    artifacts: dict[str, bool] = Field(default_factory=dict)
    evidence: str | None = None


class FlowTracker(BaseModel):
    state: StateId
    steps: list[StepStatus]
    current: StepStatus | None = None
    progress: float = 0.0
    done: bool = False


class StatusReport(BaseModel):
    project: str
    version: str
    state: StateId
    flow: FlowTracker
    tokens: dict[str, Any]
    locked: dict[str, StateId]
    logs: list[LogEntry]


class TimelineReport(BaseModel):
    ok: bool
    fps: float
    tolerance: float
    duration: float = 0.0
    video_duration: float | None = None
    video_fps: float | None = None
    cues: int = 0
    last_cue_end: float | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DraftResult(BaseModel):
    step: StepId
    draft: str
    critique: str
    revised: str
    revisions: int


class MixReport(BaseModel):
    duration: float
    loudness: float
    peak: float
    max_silence: float
