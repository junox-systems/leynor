"""Artifact bytes for one run.

Local disk now, S3 later: one contract, two implementations. Keys are posix
paths relative to the storage root, never absolute, never containing ``..``.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Protocol, runtime_checkable


class UnsafePath(ValueError):
    """A key escapes the storage root or is absolute."""


class ArtifactMissing(FileNotFoundError):
    """No bytes stored under this key."""


def safe_key(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    if not path.parts or path.is_absolute():
        raise UnsafePath(key)
    if any(part in {"..", ""} for part in path.parts):
        raise UnsafePath(key)
    return path


def artifact_key(
    organization_id: object, project_id: object, run_id: object, name: str
) -> str:
    """One artifact inside one run, scoped by org and project."""
    return "/".join(
        [str(organization_id), str(project_id), str(run_id), str(safe_key(name))]
    )


@runtime_checkable
class Store(Protocol):
    def put(self, key: str, data: bytes | str) -> str: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def tmpdir(self) -> Iterator[Path]: ...


class FileStore:
    """Writes below one root. Temp file in the target directory, then rename."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        target = (self.root / safe_key(key)).resolve()
        if target != self.root and self.root not in target.parents:
            raise UnsafePath(key)
        return target

    def put(self, key: str, data: bytes | str) -> str:
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = data.encode() if isinstance(data, str) else data
        handle, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
        try:
            with os.fdopen(handle, "wb") as fh:
                fh.write(raw)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return hashlib.sha256(raw).hexdigest()

    def get(self, key: str) -> bytes:
        try:
            return self.path(key).read_bytes()
        except FileNotFoundError:
            raise ArtifactMissing(key) from None

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    @contextmanager
    def tmpdir(self) -> Iterator[Path]:
        with tempfile.TemporaryDirectory(dir=self.root) as handle:
            yield Path(handle)
