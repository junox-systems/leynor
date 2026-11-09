"""Artifact bytes, kept in the `artifacts` Django storage.

Every process (web, the default worker, the heavy worker) reads and writes the
same bucket, so a file one step writes is there for the next step and for the
page that shows it. Keys are posix paths below one prefix, never absolute,
never containing ``..``.
"""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import IO, Protocol, runtime_checkable

from django.core.files.base import ContentFile
from django.core.files.storage import Storage, storages


class UnsafePath(ValueError):
    """A key escapes its prefix or is absolute."""


class ArtifactMissing(FileNotFoundError):
    """No bytes stored under this key."""


def safe_key(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    if not path.parts or path.is_absolute():
        raise UnsafePath(key)
    if any(part in {"..", ""} for part in path.parts):
        raise UnsafePath(key)
    return path


@runtime_checkable
class Store(Protocol):
    def put(self, key: str, data: bytes | str) -> str: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def tmpdir(self) -> Iterator[Path]: ...


class ArtifactStore:
    """One unit's artifacts: keys below `prefix` in a Django storage."""

    def __init__(self, prefix: str = "", storage: Storage | None = None):
        self.prefix = prefix.strip("/")
        self.storage = storage if storage is not None else storages["artifacts"]

    def name(self, key: str) -> str:
        key = safe_key(key).as_posix()
        return f"{self.prefix}/{key}" if self.prefix else key

    def put(self, key: str, data: bytes | str) -> str:
        """Write (or replace) one artifact. Returns its sha256."""
        raw = data.encode() if isinstance(data, str) else data
        name = self.name(key)
        # Some storages rename instead of overwriting; a step's key must not move.
        self.storage.delete(name)
        saved = self.storage.save(name, ContentFile(raw))
        if saved != name:
            raise RuntimeError(f"storage saved {key} as {saved}")
        return hashlib.sha256(raw).hexdigest()

    def get(self, key: str) -> bytes:
        with self.open(key) as handle:
            return handle.read()

    def open(self, key: str) -> IO[bytes]:
        name = self.name(key)
        if not self.storage.exists(name):
            raise ArtifactMissing(key)
        return self.storage.open(name, "rb")

    def exists(self, key: str) -> bool:
        return self.storage.exists(self.name(key))

    def size(self, key: str) -> int:
        return self.storage.size(self.name(key))

    def sha256(self, key: str) -> str:
        return hashlib.sha256(self.get(key)).hexdigest()

    def delete(self, key: str) -> None:
        self.storage.delete(self.name(key))

    def delete_all(self) -> None:
        """Every artifact under the prefix."""
        if not self.prefix:
            raise UnsafePath("refusing to delete a whole storage")
        pending = [self.prefix]
        while pending:
            folder = pending.pop()
            try:
                folders, files = self.storage.listdir(folder)
            except FileNotFoundError:  # nothing was ever written here
                continue
            pending += [f"{folder}/{name}" for name in folders]
            for name in files:
                self.storage.delete(f"{folder}/{name}")

    @contextmanager
    def tmpdir(self) -> Iterator[Path]:
        """Local scratch space: ffmpeg, Chromium and whisper need real files."""
        with tempfile.TemporaryDirectory(prefix="artifact-") as handle:
            yield Path(handle)
