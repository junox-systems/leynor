"""HyperFrames and ffmpeg calls. Subprocess only: nothing heavy is imported."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

from apps.renders.timeline import probe_duration

HYPERFRAMES = "hyperframes@0.8.188"


class VideoError(RuntimeError):
    pass


class RenderResult(BaseModel):
    path: str
    sha256: str
    duration: float | None = None
    fps: float | None = None


def npx(args: list[str], cwd: Path) -> str:
    if shutil.which("npx") is None:
        raise VideoError("npx is not installed; hyperframes needs node")
    result = subprocess.run(
        ["npx", "--yes", HYPERFRAMES, *args], cwd=cwd, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise VideoError(
            f"hyperframes {' '.join(args)} failed:\n{result.stderr[-1200:]}"
        )
    return result.stdout + result.stderr


def check(workdir: Path) -> str:
    return npx(["check", "."], workdir)


def encode(workdir: Path, quality: str = "delivery") -> Path:
    npx(["render", "--quality", quality, "--output", "out.mp4"], workdir)
    rendered = workdir / "out.mp4"
    if not rendered.exists():
        raise VideoError("render finished but out.mp4 is missing")
    return rendered


def fit(rendered: Path, duration: float | None, fps: int, scratch: Path) -> Path:
    """HyperFrames can emit a few trailing frames. Cut to the master once."""
    if duration is None:
        return rendered
    length = probe_duration(rendered)
    if length is None or length <= duration + 1 / fps:
        return rendered
    fitted = scratch / "fit.mp4"
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(rendered),
            "-t",
            f"{duration:.3f}",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(fitted),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not fitted.exists():
        raise VideoError(
            f"could not fit the render to the master: {result.stderr[-400:]}"
        )
    return fitted
