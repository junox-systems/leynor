"""Look, compose, print: the visual half, over a Store. No ORM."""

from __future__ import annotations

from apps.projects.spec import ReelSpec
from apps.renders.compose import compose
from apps.renders.media import Procedural
from apps.renders.timeline import check_summary
from apps.renders.video import RenderResult, check, encode, fit
from apps.voices.cues import CueData


class RenderError(RuntimeError):
    pass


def run_look(spec: ReelSpec, store, *, tool: Procedural | None = None) -> list[dict]:
    tool = tool or Procedural()
    written = []
    for index, scene in enumerate(spec.scenes, start=1):
        visual = tool.render(spec.slug, scene, index)
        key = f"assets/visuals/s{index}.{visual.ext}"
        sha = store.put(key, visual.data)
        written.append(
            {
                "index": index,
                "key": key,
                "sha": sha,
                "tool": visual.tool,
                "tool_version": visual.tool_version,
                "seed": visual.seed,
            }
        )

    credits = [
        "# CREDITS",
        "",
        "All visuals generated locally. No third-party media.",
        "",
    ]
    credits += [
        f"- s{row['index']}: {row['tool']} {row['tool_version']}, "
        f"seed {row['seed']}, {row['sha'][:12]}"
        for row in written
    ]
    store.put("assets/CREDITS.md", "\n".join(credits) + "\n")
    return written


def run_compose(
    spec: ReelSpec,
    cues: list[CueData],
    total: float,
    visuals: dict[int, list[str]],
    store,
) -> list[str]:
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
