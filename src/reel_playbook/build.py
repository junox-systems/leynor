"""The pipeline: spec in, gated project out.

Every step writes its artifact into the database, records gate evidence, and
moves the state machine forward. The only file written is ``out.mp4``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .align import AlignError, FasterWhisper, write_cues
from .book import ReelPlaybook, StateError
from .compose import compose
from .content import ReelSpec, load_spec
from .creative import validate_beats, validate_hooks, validate_idea
from .design import default_frame
from .imagetools import Procedural, Waveform
from .steps import STEPS
from .storage import Workspace, now
from .timeline import probe_duration
from .tts import PocketTTS
from .voice import MixError, MixReport, mix, synthesize_master

HYPERFRAMES = "hyperframes@0.8.188"
WORDS_PER_SECOND = 2.5
LEGACY_STEPS = {"assets": "look", "compose": "voice", "render": "print"}
LEGACY_LOCKS = {"ASSETS": "VOICE", "COMPOSE": "VOICE", "RENDER": "PRINT"}
TEXT_SUFFIX = {".md", ".html", ".json", ".txt", ".svg", ".csv"}
KEEP = {"out.mp4"}


class BuildError(RuntimeError):
    pass


def build(
    workspace: Workspace,
    target: str,
    *,
    whisper_size: str = "base.en",
    threads: int = 4,
    render: bool = True,
    quality: str = "delivery",
) -> ReelPlaybook:
    path = Path(target)
    if path.suffix == ".json" and path.exists():
        spec = load_spec(path)
        book = _prepare(workspace, spec)
        store_spec(book, spec)
    else:
        book = ReelPlaybook.open(workspace, target)
        spec = stored_spec(book)
        if book.state != "IDEA":
            book.rewind("idea", "rebuild from stored spec", keep_creative=True)

    idea = book.idea()
    problems = validate_idea(idea)
    if problems:
        raise BuildError("idea gate: " + "; ".join(problems))
    book.pass_gate(
        "idea",
        f"score {float(idea['score']):g}/10, goal {idea['goal']}, "
        f"{len(idea['citations'])} citations, {len(idea['alternatives'])} rejected "
        f"concepts, objection answered",
    )

    hooks = book.hooks()
    problems = validate_hooks(hooks)
    if problems:
        raise BuildError("hook gate: " + "; ".join(problems))
    chosen = next(row for row in hooks if row["chosen"])
    archetypes = {row["archetype"] for row in hooks}
    book.pass_gate(
        "hook",
        f"{len(hooks)} hooks across {len(archetypes)} archetypes, winner "
        f"{chosen['overlay']!r} ({len(chosen['overlay'].split())} words), "
        f"objection answered",
    )

    beats = book.beats()
    problems = validate_beats(beats, spec)
    if problems:
        raise BuildError("board gate: " + "; ".join(problems))
    write_board(book, spec, beats)
    if book.text("frame.md") is None:
        book.put_text("frame.md", default_frame(book.design()))
    purposes = [str(row["purpose"]).lower() for row in beats]
    planned = sum(float(row["seconds_est"]) for row in beats)
    book.pass_gate(
        "board",
        f"{len(beats)} beats, turn at {purposes.index('turn') + 1}, payoff at "
        f"{purposes.index('payoff') + 1}, planned {planned:.1f}s against a "
        f"{spec.target_seconds}s target, every scene has a visual beat",
    )

    run_look(book, spec)
    book.pass_gate(
        "look",
        f"{len(spec.scenes)} procedural plates, seeds pinned, credits written, "
        "9:16 at 1080x1920",
    )

    report = run_voice(book, spec, whisper_size=whisper_size, threads=threads)
    cues = book.cues()
    book.pass_gate(
        "voice",
        f"one master {report.duration:.2f}s at {report.loudness:.1f} LUFS / "
        f"{report.peak:.1f} dBTP, {len(cues)} cues, max silence "
        f"{report.max_silence:.2f}s",
    )

    run_waveforms(book, spec)
    run_compose(book, spec)

    if not render:
        return book

    run_check(book)
    run_render(book, quality=quality)
    timeline = book.timeline(video="out.mp4")
    if not timeline.ok:
        book.fail_gate("print", "; ".join(timeline.errors))
        raise BuildError("; ".join(timeline.errors))
    book.pass_gate(
        "print",
        f"check 0 errors, out.mp4 {timeline.video_duration:.3f}s at "
        f"{timeline.video_fps:g}fps, master {timeline.duration:.3f}s, "
        f"{timeline.cues} cues on time",
    )
    return book


def stored_spec(book: ReelPlaybook) -> ReelSpec:
    raw = book.text("spec.json")
    if raw is None:
        raise BuildError(f"{book.slug} has no spec.json; import one first")
    return ReelSpec.model_validate(json.loads(raw))


def store_spec(book: ReelPlaybook, spec: ReelSpec) -> None:
    book.put_text("spec.json", json.dumps(spec.model_dump(), indent=2), kind="spec")


def _prepare(workspace: Workspace, spec: ReelSpec) -> ReelPlaybook:
    if workspace.catalog().get_project(spec.slug) is not None:
        book = ReelPlaybook.open(workspace, spec.slug)
        if book.state != "IDEA":
            book.rewind("idea", "rebuild from spec", keep_creative=True)
        return book
    return _create_fresh(
        workspace,
        spec.slug,
        size=(1080, 1920),
        language=spec.tts_model,
        tts_model=spec.tts_model,
    )


def write_board(
    book: ReelPlaybook, spec: ReelSpec, beats: list[dict] | None = None
) -> None:
    beats = beats or []
    lines = ["# STORYBOARD", ""]
    cursor = 0.0
    for index, scene in enumerate(spec.scenes, start=1):
        beat = beats[index - 1] if index <= len(beats) else {}
        estimate = float(beat.get("seconds_est") or len(scene.narration.split()) / WORDS_PER_SECOND)
        lines += [
            f"## Frame {index}: {scene.overlay} ({cursor:.2f}-{cursor + estimate:.2f} s est)",
            f"- purpose: {beat.get('purpose', '-')}",
            f"- narration: {scene.narration}",
            f"- on-screen: {scene.overlay}",
            f"- label: {scene.label}",
            f"- visual beat: {beat.get('visual_beat', 'procedural plate')}",
            f"- estimated: {estimate:.2f}s",
            "",
        ]
        cursor = round(cursor + estimate, 2)
    lines += ["Durations are estimates until step 5. The voice is the clock.", ""]
    book.put_text("STORYBOARD.md", "\n".join(lines))

    rows = "".join(
        f"<tr><td>{i}</td><td>{_esc(scene.overlay)}</td>"
        f"<td>{_esc(scene.label)}</td><td>{_esc(scene.narration)}</td></tr>"
        for i, scene in enumerate(spec.scenes, start=1)
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="UTF-8" /><title>{_esc(spec.title)}</title>
<style>body{{background:#0b0b0c;color:#f2efe6;font-family:Arial,sans-serif;padding:48px}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #2a2a2e;
padding:14px;text-align:left;vertical-align:top}}th{{color:#e0a33e;font-size:13px;
letter-spacing:.14em;text-transform:uppercase}}</style></head>
<body><h1>{_esc(spec.title)}</h1>
<table><tr><th>#</th><th>overlay</th><th>label</th><th>narration</th></tr>{rows}</table>
</body></html>
"""
    book.put_text("boards/storyboard.html", html)


def run_look(book: ReelPlaybook, spec: ReelSpec) -> list[dict]:
    tool = Procedural()
    written = []
    for index, scene in enumerate(spec.scenes, start=1):
        visual = tool.render(spec.slug, scene, index)
        path = f"assets/visuals/s{index}.{visual.ext}"
        sha = book.put_bytes(
            path,
            visual.data,
            visual.ext,
            kind="visual",
            media_type=visual.media_type,
            meta={
                "tool": visual.tool,
                "tool_version": visual.tool_version,
                "seed": visual.seed,
                "scene": index,
            },
        )
        key = book.store.key(visual.tool, visual.tool_version, visual.seed, index)
        book.catalog.cache_put(key, sha, visual.tool, visual.tool_version)
        written.append({"index": index, "sha": sha, "path": path, "visual": visual})

    credits = ["# CREDITS", "", "All visuals generated locally. No third-party media.", ""]
    credits += [
        f"- s{row['index']}: {row['visual'].tool} {row['visual'].tool_version}, "
        f"seed {row['visual'].seed}, {row['sha'][:12]}"
        for row in written
    ]
    book.put_text("assets/CREDITS.md", "\n".join(credits) + "\n")
    return written


def run_voice(
    book: ReelPlaybook,
    spec: ReelSpec,
    *,
    whisper_size: str = "base.en",
    threads: int = 4,
) -> MixReport:
    voice = book.tokens.voice or spec.voice
    model = book.tokens.tts_model or spec.tts_model
    if book.tokens.voice != voice:
        book.set_token("voice", voice)
    if book.tokens.tts_model != model:
        book.set_token("tts_model", model)

    spoken = _spoken(spec)
    with book.workspace.scratch() as scratch:
        raw = scratch / "master.raw.wav"
        master = scratch / "voice.wav"
        synthesize_master(PocketTTS(model=model), spoken, voice, raw)
        report = mix(raw, master, scratch)

        try:
            result = FasterWhisper(size=whisper_size, threads=threads).align(master, spec)
        except AlignError:
            raise
        expected = len(spec.sentences())
        if len(result.cues) != expected:
            raise BuildError(
                f"aligner returned {len(result.cues)} cues, expected {expected}"
            )
        book.put_bytes(
            "assets/voice.wav",
            master.read_bytes(),
            "wav",
            kind="audio",
            media_type="audio/wav",
            meta={
                "voice": voice,
                "tts_model": model,
                "loudness": report.loudness,
                "peak": report.peak,
                "coverage": result.coverage,
                "backend": result.backend,
            },
        )
        captions = scratch / "captions.json"
        write_cues(captions, result.cues)
        book.put_text("captions.json", captions.read_text(), kind="captions")
    book.catalog.put_cues(book.slug, result.cues)
    book.set_token("duration", round(report.duration, 3))
    return report


def run_waveforms(book: ReelPlaybook, spec: ReelSpec) -> list[dict]:
    cues = book.cue_dicts()
    written = []
    master = book.read("assets/voice.wav")
    if master is None:
        return written
    for index, scene in enumerate(spec.scenes, start=1):
        if not scene.waveform:
            continue
        span = [cue for cue in cues if int(cue["scene"]) == index]
        if not span:
            continue
        start = min(float(cue["start"]) for cue in span)
        end = max(float(cue["end"]) for cue in span)
        with book.workspace.scratch() as scratch:
            source = scratch / "voice.wav"
            source.write_bytes(master)
            visual = Waveform().render(spec.slug, index, source, start, end, scratch)
        path = f"assets/visuals/s{index}-wave.{visual.ext}"
        book.put_bytes(
            path,
            visual.data,
            visual.ext,
            kind="visual",
            media_type=visual.media_type,
            meta={"tool": visual.tool, "tool_version": visual.tool_version,
                  "seed": visual.seed, **visual.meta},
        )
        written.append({"index": index, "path": path})
    return written


def run_compose(book: ReelPlaybook, spec: ReelSpec) -> dict[str, Path]:
    total = book.tokens.duration
    if total is None:
        raise BuildError("no duration; run the voice step first")
    visuals: dict[int, list[str]] = {}
    for index in range(1, len(spec.scenes) + 1):
        plates = sorted(
            row["path"]
            for row in book.artifacts()
            if row["path"].startswith(f"assets/visuals/s{index}.")
        )
        plates += sorted(
            row["path"]
            for row in book.artifacts()
            if row["path"].startswith(f"assets/visuals/s{index}-")
        )
        visuals[index] = plates
    with book.workspace.scratch() as scratch:
        written = compose(scratch, spec, book.cue_dicts(), float(total), visuals)
        for path in written.values():
            relative = str(path.relative_to(scratch))
            book.put_text(relative, path.read_text(), kind="composition")
    return written


def run_check(book: ReelPlaybook) -> str:
    with book.workspace.scratch() as scratch:
        book.materialize(scratch)
        output = _npx(["check", "."], scratch)
    errors, warnings = check_summary(output)
    if errors or warnings:
        raise BuildError(f"hyperframes check: {errors} errors, {warnings} warnings")
    return output


def check_summary(output: str) -> tuple[int, int]:
    """Read the `N error(s), M warning(s)` line; silence is a failure."""
    match = re.search(r"(\d+) error\(s\), (\d+) warning\(s\)", output)
    if not match:
        raise BuildError("hyperframes check printed no summary line")
    return int(match.group(1)), int(match.group(2))


def run_render(book: ReelPlaybook, *, quality: str = "delivery") -> Path:
    with book.workspace.scratch() as scratch:
        book.materialize(scratch)
        _npx(["render", "--quality", quality, "--output", "out.mp4"], scratch)
        rendered = scratch / "out.mp4"
        if not rendered.exists():
            raise BuildError("render finished but out.mp4 is missing")
        rendered = _fit_video(rendered, book.tokens.duration, book.tokens.fps, scratch)
        shutil.copy2(rendered, book.render_path)
    book.catalog.put_render(
        book.slug,
        {
            "sha256": book.store.sha(book.render_path.read_bytes()),
            "duration_s": book.tokens.duration,
            "fps": float(book.tokens.fps),
            "loudness": None,
            "peak": None,
            "verified_at": now(),
        },
    )
    return book.render_path


def _fit_video(rendered: Path, duration: float | None, fps: int, scratch: Path) -> Path:
    """HyperFrames can emit a few extra trailing frames. Cut to the master once."""
    if duration is None:
        return rendered
    length = probe_duration(rendered)
    if length is None or length <= duration + 1 / fps:
        return rendered
    fitted = scratch / "fit.mp4"
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(rendered), "-t", f"{duration:.3f}",
         "-c", "copy", "-movflags", "+faststart", str(fitted)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not fitted.exists():
        raise BuildError(f"could not fit the render to the master: {result.stderr[-400:]}")
    return fitted


def run_gate_check(book: ReelPlaybook, *, video: str | None = None) -> bool:
    report = book.timeline(video=video)
    if report.ok:
        book.pass_gate("print", _evidence(report))
    else:
        book.fail_gate("print", "; ".join(report.errors))
    return report.ok


def import_project(workspace: Workspace, path: Path | str) -> ReelPlaybook:
    """Ingest a project directory: 0.0.1 (STATE.json) or 0.1.0 (files)."""
    source = Path(path).resolve()
    if not source.is_dir():
        raise BuildError(f"{source} is not a directory")
    legacy = source / "STATE.json"
    snapshot = None
    if not legacy.exists():
        snapshot = workspace.tmp / f"import-{source.name}"
        shutil.rmtree(snapshot, ignore_errors=True)
        shutil.copytree(source, snapshot, ignore=shutil.ignore_patterns("out.mp4"))
    if legacy.exists():
        book = _import_state(workspace, source, json.loads(legacy.read_text()))
    elif workspace.catalog().get_project(source.name) is not None:
        book = ReelPlaybook.open(workspace, source.name)
    else:
        spec_file = workspace.root / "specs" / f"{source.name}.json"
        if not spec_file.exists():
            raise BuildError(f"{source.name} is not in the database and has no spec")
        spec = load_spec(spec_file)
        book = _create_fresh(
            workspace,
            spec.slug,
            size=(1080, 1920),
            language=spec.tts_model,
            tts_model=spec.tts_model,
        )
        store_spec(book, spec)

    spec_file = workspace.root / "specs" / f"{book.slug}.json"
    if book.text("spec.json") is None and spec_file.exists():
        store_spec(book, load_spec(spec_file))

    _ingest_dir(book, snapshot or source)
    if snapshot is not None:
        shutil.rmtree(snapshot, ignore_errors=True)
    if source != book.root and (source / "out.mp4").exists():
        shutil.copy2(source / "out.mp4", book.render_path)
    book.save()
    _prune(book.root)
    return book


def _import_state(workspace: Workspace, source: Path, legacy: dict) -> ReelPlaybook:
    slug = source.name
    if workspace.catalog().get_project(slug) is not None:
        return ReelPlaybook.open(workspace, slug)

    tokens = legacy.get("tokens", {})
    book = _create_fresh(
        workspace,
        slug,
        fps=int(tokens.get("fps", 30)),
        size=(int(tokens.get("width", 1080)), int(tokens.get("height", 1920))),
        language=str(tokens.get("language", "english")),
        tts_model=str(tokens.get("tts_model", "english")),
        max_attempts=int(legacy.get("max_attempts", 3)),
    )
    for key in ("duration", "voice", "tts_model"):
        if tokens.get(key) is not None:
            book.tokens.set(key, tokens[key])
    book.locked_at = _legacy_locks(legacy.get("locked_at", {}))
    for gate_id, gate in legacy.get("gates", {}).items():
        step = gate_id if gate_id in {spec.id for spec in STEPS} else LEGACY_STEPS.get(gate_id)
        if step is not None:
            book._gates[step] = _legacy_gate(step, gate)
    book.state = legacy.get("state", "DONE")
    cues = _legacy_cues(source)
    if cues:
        book.catalog.put_cues(slug, cues)
    book.save()
    return book


def _ingest_dir(book: ReelPlaybook, source: Path) -> None:
    for item in sorted(source.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(source)
        if str(relative) in KEEP or relative.parts[0] in {"tmp", "__pycache__"}:
            continue
        if str(relative) == "manifest.json":
            continue
        ext = item.suffix.lower()
        if ext in TEXT_SUFFIX:
            book.put_text(str(relative), item.read_text())
        elif ext in {".wav", ".png", ".jpg", ".jpeg", ".webp", ".mp4"}:
            kind = {".wav": "audio", ".mp4": "video"}.get(ext, "visual")
            book.put_bytes(
                str(relative), item.read_bytes(), ext.lstrip("."), kind=kind
            )


def _create_fresh(workspace: Workspace, slug: str, **kwargs) -> ReelPlaybook:
    """Create a project, keeping a render that is already in the folder."""
    target = workspace.project_dir(slug)
    keep = (target / "out.mp4").read_bytes() if (target / "out.mp4").exists() else None
    _prune(target)
    (target / "out.mp4").unlink(missing_ok=True)
    book = ReelPlaybook.create(workspace, slug, **kwargs)
    if keep is not None:
        (target / "out.mp4").write_bytes(keep)
    return book


def _prune(root: Path) -> None:
    for item in root.iterdir():
        if item.name in KEEP:
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink()


def _legacy_locks(locks: dict) -> dict:
    from .steps import STATES

    out = {}
    for key, value in locks.items():
        out[key] = value if value in STATES else LEGACY_LOCKS.get(value, "VOICE")
    return out


def _legacy_gate(step: str, gate: dict):
    from .models import GateRecord, utcnow

    at = gate.get("at")
    parsed = None
    if isinstance(at, str):
        from datetime import datetime

        try:
            parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            parsed = utcnow()
    return GateRecord(
        step=step,
        result=gate.get("result"),
        attempts=int(gate.get("attempts") or 0),
        evidence=gate.get("evidence"),
        reason=gate.get("reason"),
        at=parsed,
    )


def _legacy_cues(source: Path) -> list[dict]:
    """Cues from a 0.0.1 STORYBOARD.md: frame heading plus narration line."""
    board = source / "STORYBOARD.md"
    if not board.exists():
        return []

    cues: list[dict] = []
    scene, span = 0, None
    for line in board.read_text().splitlines():
        heading = re.match(
            r"^## Frame (\d+):.*\((\d+(?:\.\d+)?)-(\d+(?:\.\d+)?) s\)", line
        )
        if heading:
            scene = int(heading.group(1))
            span = (float(heading.group(2)), float(heading.group(3)))
            continue
        narration = line.removeprefix("- narration:").strip()
        if scene and span and line.startswith("- narration:") and narration:
            cues.append(
                {"scene": scene, "start": span[0], "end": span[1], "text": narration}
            )
            scene, span = 0, None
    return cues


def _spoken(spec: ReelSpec) -> str:
    script = spec.script()
    for written, said in spec.pronounce.items():
        script = script.replace(written, said)
    return script


def _evidence(report) -> str:
    return (
        f"check 0 errors, out.mp4 {report.video_duration:.3f}s, master "
        f"{report.duration:.3f}s, {report.cues} cues, last cue "
        f"{report.last_cue_end:.3f}s"
    )


def _npx(args: list[str], cwd: Path) -> str:
    if shutil.which("npx") is None:
        raise BuildError("npx is not installed; hyperframes needs node")
    result = subprocess.run(
        ["npx", "--yes", HYPERFRAMES, *args], cwd=cwd, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise BuildError(
            f"hyperframes {' '.join(args)} failed:\n{result.stderr[-1200:]}"
        )
    return result.stdout + result.stderr


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


__all__ = [
    "BuildError",
    "MixError",
    "StateError",
    "build",
    "import_project",
    "run_check",
    "run_compose",
    "run_gate_check",
    "run_look",
    "run_render",
    "run_voice",
    "run_waveforms",
    "store_spec",
    "stored_spec",
    "write_board",
]
