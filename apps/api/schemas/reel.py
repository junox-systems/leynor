# apps/api/schemas/reel.py

import uuid

import msgspec


class RunUrlsSchema(msgspec.Struct):
    status: str
    page: str


class RunStatusSchema(msgspec.Struct):
    """Where a pitch or a reel's route is now. Same shape the page renders from."""

    kind: str
    status: str
    step: str
    started: str
    error: str
    version: str
    urls: RunUrlsSchema


class ReelPathParams(msgspec.Struct):
    reel_id: uuid.UUID


class PitchPathParams(msgspec.Struct):
    pitch_id: uuid.UUID
