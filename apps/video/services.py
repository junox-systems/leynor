"""Compose and print: a spec plus its assets become one mp4. No ORM."""

from __future__ import annotations

from apps.video.audio.cues import CueData
from apps.video.compose import compose
from apps.video.encode import RenderResult, check, encode, fit
from apps.video.spec import ReelSpec
from apps.video.timeline import check_summary


class RenderError(RuntimeError):
    pass


def run_compose(
    spec: ReelSpec,
    cues: list[CueData],
    total: float,
    visuals: dict[int, list[str]],
    store,
) -> list[str]:
    """Write the composition tree and copy every file into the store."""
    with store.tmpdir() as scratch:
        written = compose(
            scratch,
            spec,
            [cue.model_dump() for cue in cues],
            total,
            visuals,
        )
        keys = []
        for path in written.values():
            key = path.relative_to(scratch).as_posix()
            store.put(key, path.read_text())
            keys.append(key)
    return keys


def run_print(
    store,
    keys: list[str],
    *,
    duration: float | None = None,
    fps: int = 30,
    quality: str = "delivery",
) -> RenderResult:
    """Check the composition, encode it, and keep the mp4 under `out.mp4`."""
    with store.tmpdir() as scratch:
        for key in keys:
            target = scratch / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(store.get(key))

        output = check(scratch)
        errors, warnings = check_summary(output)
        if errors or warnings:
            raise RenderError(
                f"hyperframes check: {errors} errors, {warnings} warnings"
            )

        rendered = fit(encode(scratch, quality), duration, fps, scratch)
        sha = store.put("out.mp4", rendered.read_bytes())

    return RenderResult(path="out.mp4", sha256=sha, duration=duration, fps=float(fps))
