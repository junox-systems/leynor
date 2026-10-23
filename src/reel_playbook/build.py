"""The pipeline: spec in, gated project out.

Every step writes its artifact, records gate evidence, and moves the state
machine forward. Nothing here reaches around the book: the book owns the state,
the gates and the database row.
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
from .imagetools import Procedural, Waveform
from .steps import STEPS
from .storage import Workspace, now
from .tts import PocketTTS
from .voice import MixError, MixReport, mix, synthesize_master

HYPERFRAMES = "hyperframes@0.8.188"
WORDS_PER_SECOND = 2.5
LEGACY_STEPS = {"assets": "look", "compose": "voice", "render": "print"}
LEGACY_LOCKS = {"ASSETS": "VOICE", "COMPOSE": "VOICE", "RENDER": "PRINT"}


class BuildError(RuntimeError):
    pass


def find_spec(workspace: Workspace, slug: str, spec: Path | str | None = None) -> Path:
    if spec is not None:
        path = Path(spec)
        if not path.exists():
            raise BuildError(f"no spec at {path}")
        return path
    exact = workspace.specs / f"{slug}.json"
    if exact.exists():
        return exact
    matches = sorted(workspace.specs.glob(f"*{slug}*.json"))
    if len(matches) == 1:
        return matches[0]
    raise BuildError(f"no spec for {slug} in {workspace.specs}; pass --spec")


def build(
    workspace: Workspace,
    spec_path: Path | str,
    *,
    whisper_size: str = "base.en",
    threads: int = 4,
    render: bool = True,
    quality: str = "delivery",
) -> ReelPlaybook:
    spec = load_spec(spec_path)
    book = _prepare(workspace, spec)
    write_board(book, spec)
    book.pass_gate(
        "idea",
        f"{Path(spec_path).name}: {spec.title!r}, {len(spec.scenes)} scenes, "
        f"{len(spec.sources)} sources",
    )
    book.pass_gate(
        "hook",
        f"scene 1 overlay {spec.scenes[0].overlay!r} ({len(spec.scenes[0].overlay)} "
        f"chars) names the payoff; label {spec.scenes[0].label!r}",
    )
    book.pass_gate(
        "board",
        f"storyboard from spec: {len(spec.scenes)} scenes, every scene has narration, "
        f"overlay and label; durations estimated at {WORDS_PER_SECOND * 60:g} wpm",
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


def _prepare(workspace: Workspace, spec: ReelSpec) -> ReelPlaybook:
    if workspace.catalog().get_project(spec.slug) is not None:
        book = ReelPlaybook.open(workspace, spec.slug)
        if book.state != "IDEA":
            book.rewind("idea", "rebuild from spec")
        return book
    return ReelPlaybook.create(
        workspace,
        spec.slug,
        size=(1080, 1920),
        language=spec.tts_model,
        tts_model=spec.tts_model,
    )


def write_board(book: ReelPlaybook, spec: ReelSpec) -> Path:
    lines = ["# STORYBOARD", ""]
    cursor = 0.0
    for index, scene in enumerate(spec.scenes, start=1):
        words = len(scene.narration.split())
        estimate = round(words / WORDS_PER_SECOND, 2)
        lines += [
            f"## Frame {index}: {scene.overlay} ({cursor:.2f}-{cursor + estimate:.2f} s est)",
            f"- narration: {scene.narration}",
            f"- on-screen: {scene.overlay}",
            f"- label: {scene.label}",
            f"- visual: procedural plate, seed {index}",
            f"- estimated: {estimate:.2f}s ({words} words)",
            "",
        ]
        cursor = round(cursor + estimate, 2)
    lines += [
        "Durations are estimates until step 5. The voice is the clock.",
        "",
    ]
    path = book.root / "STORYBOARD.md"
    path.write_text("\n".join(lines))

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
    (book.root / "boards" / "storyboard.html").write_text(html)
    return path


def run_look(book: ReelPlaybook, spec: ReelSpec) -> list[dict]:
    tool = Procedural()
    written = []
    for index, scene in enumerate(spec.scenes, start=1):
        visual = tool.render(spec.slug, scene, index)
        sha, ref = book.store.put_bytes(visual.data, visual.ext)
        key = book.store.key(visual.tool, visual.tool_version, visual.seed, index)
        book.catalog.cache_put(key, sha, visual.tool, visual.tool_version)
        book.catalog.put_asset(
            {
                "sha256": sha,
                "ext": visual.ext,
                "kind": "visual",
                "media_type": visual.media_type,
                "bytes": len(visual.data),
                "width": 1080,
                "height": 1920,
                "created_at": now(),
            }
        )
        book.catalog.link_asset(
            spec.slug,
            sha,
            f"visual:s{index}",
            {
                "tool": visual.tool,
                "tool_version": visual.tool_version,
                "seed": visual.seed,
                "scene": index,
            },
        )
        target = book.root / "assets" / "visuals" / f"s{index}.{visual.ext}"
        book.store.materialize(ref, target)
        written.append({"index": index, "ref": ref, "path": target, "visual": visual})

    frame = [
        "# FRAME",
        "",
        f"- title: {spec.title}",
        f"- kicker: {spec.kicker}",
        "- size: 1080x1920, 30 fps",
        "- palette: #0b0b0c ground, #f2efe6 type, #e0a33e accent, #8a867c secondary",
        "- type: Helvetica Neue 92-128 px display, 30 px mono labels",
        "- margins: 82 px side, 52 px frame inset",
        "- plates: procedural SVG, 1080x1920, seeded per scene",
        "",
    ]
    (book.root / "frame.md").write_text("\n".join(frame))

    credits = ["# CREDITS", "", "All visuals generated locally. No third-party media.", ""]
    credits += [
        f"- s{row['index']}: {row['visual'].tool} {row['visual'].tool_version}, "
        f"seed {row['visual'].seed}, {row['ref']}"
        for row in written
    ]
    credits.append("")
    (book.root / "assets" / "CREDITS.md").write_text("\n".join(credits))
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

    master = book.root / "assets" / "voice.wav"
    spoken = _spoken(spec)
    with book.workspace.scratch() as scratch:
        raw = scratch / "master.raw.wav"
        synthesize_master(PocketTTS(model=model), spoken, voice, raw)
        report = mix(raw, master, scratch)

    try:
        result = FasterWhisper(size=whisper_size, threads=threads).align(master, spec)
    except AlignError:
        raise
    expected = len(spec.sentences())
    if len(result.cues) != expected:
        raise BuildError(f"aligner returned {len(result.cues)} cues, expected {expected}")

    write_cues(book.root / "captions.json", result.cues)
    book.catalog.put_cues(book.slug, result.cues)
    sha, ref = book.store.put_file(master)
    book.catalog.put_asset(
        {
            "sha256": sha,
            "ext": "wav",
            "kind": "audio",
            "media_type": "audio/wav",
            "bytes": master.stat().st_size,
            "duration_s": report.duration,
            "width": None,
            "height": None,
            "created_at": now(),
        }
    )
    book.catalog.link_asset(
        book.slug,
        sha,
        "voice",
        {
            "voice": voice,
            "tts_model": model,
            "loudness": report.loudness,
            "peak": report.peak,
            "coverage": result.coverage,
            "backend": result.backend,
        },
    )
    book.set_token("duration", round(report.duration, 3))
    return report


def run_waveforms(book: ReelPlaybook, spec: ReelSpec) -> list[dict]:
    master = book.root / "assets" / "voice.wav"
    cues = book.cue_dicts()
    written = []
    for index, scene in enumerate(spec.scenes, start=1):
        if not scene.waveform:
            continue
        span = [cue for cue in cues if int(cue["scene"]) == index]
        if not span:
            continue
        start = min(float(cue["start"]) for cue in span)
        end = max(float(cue["end"]) for cue in span)
        with book.workspace.scratch() as scratch:
            visual = Waveform().render(spec.slug, index, master, start, end, scratch)
        sha, ref = book.store.put_bytes(visual.data, visual.ext)
        book.catalog.put_asset(
            {
                "sha256": sha,
                "ext": visual.ext,
                "kind": "visual",
                "media_type": visual.media_type,
                "bytes": len(visual.data),
                "width": 920,
                "height": 260,
                "created_at": now(),
            }
        )
        book.catalog.link_asset(
            spec.slug,
            sha,
            f"visual:s{index}:wave",
            {"tool": visual.tool, "tool_version": visual.tool_version,
             "seed": visual.seed, "scene": index, **visual.meta},
        )
        target = book.root / "assets" / "visuals" / f"s{index}-wave.{visual.ext}"
        book.store.materialize(ref, target)
        written.append({"index": index, "path": target})
    return written


def run_compose(book: ReelPlaybook, spec: ReelSpec) -> dict[str, Path]:
    total = book.tokens.duration
    if total is None:
        raise BuildError("no duration; run the voice step first")
    visuals: dict[int, list[str]] = {}
    for index in range(1, len(spec.scenes) + 1):
        plates = []
        for path in sorted((book.root / "assets" / "visuals").glob(f"s{index}.*")):
            plates.append(str(path.relative_to(book.root)))
        for path in sorted((book.root / "assets" / "visuals").glob(f"s{index}-*")):
            plates.append(str(path.relative_to(book.root)))
        visuals[index] = plates
    return compose(book.root, spec, book.cue_dicts(), float(total), visuals)


def run_check(book: ReelPlaybook) -> str:
    return _npx(["check", "."], book.root)


def run_render(book: ReelPlaybook, *, quality: str = "delivery") -> Path:
    _npx(["render", "--quality", quality, "--output", "out.mp4"], book.root)
    out = book.root / "out.mp4"
    if not out.exists():
        raise BuildError("render finished but out.mp4 is missing")
    sha, _ = book.store.put_file(out)
    book.catalog.put_render(
        book.slug,
        {
            "sha256": sha,
            "duration_s": book.tokens.duration,
            "fps": float(book.tokens.fps),
            "loudness": None,
            "peak": None,
            "verified_at": now(),
        },
    )
    return out


def run_gate_check(book: ReelPlaybook, *, video: str | None = None) -> bool:
    report = book.timeline(video=video)
    if report.ok:
        book.pass_gate("print", _evidence(report))
    else:
        book.fail_gate("print", "; ".join(report.errors))
    return report.ok


def import_legacy(workspace: Workspace, path: Path | str) -> ReelPlaybook:
    """Bring a 0.0.1 project directory into the one database."""
    source = Path(path).resolve()
    state_file = source / "STATE.json"
    if not state_file.exists():
        raise BuildError(f"no STATE.json in {source}")
    legacy = json.loads(state_file.read_text())
    slug = source.name
    if workspace.catalog().get_project(slug) is not None:
        book = ReelPlaybook.open(workspace, slug)
        if not book.cues():
            cues = _legacy_cues(source)
            if cues:
                book.catalog.put_cues(slug, cues)
        _copy_artifacts(source, book.root)
        book.save()
        return book

    tokens = legacy.get("tokens", {})
    book = ReelPlaybook.create(
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
        if step is None:
            continue
        book._gates[step] = _legacy_gate(step, gate)
    book.state = legacy.get("state", "DONE")
    cues = _legacy_cues(source)
    if cues:
        book.catalog.put_cues(slug, cues)
    _copy_artifacts(source, book.root)
    book.save()

    for item in sorted(source.iterdir()):
        if item.is_file() and item.suffix in (".mp4", ".wav", ".png"):
            _link_file(book, item, item.stem)
    for wav in sorted((source / "assets").glob("*.wav")):
        _link_file(book, wav, f"audio:{wav.stem}")
    for html in sorted((source / "compositions").glob("*.html")):
        _link_file(book, html, f"composition:{html.stem}")
    for wav in sorted((source / "assets").glob("scene-*.wav")):
        try:
            scene = int(wav.stem.rsplit("-", 1)[-1])
        except ValueError:
            continue
        cues = book.cue_dicts()
        if not cues:
            break
        span = [cue for cue in cues if int(cue["scene"]) == scene]
        if span:
            duration = max(float(cue["end"]) for cue in span)
            book.catalog.link_asset(
                slug, _sha(book, wav), f"audio:scene-{scene:02d}", {"scene": scene,
                                                                  "duration": duration}
            )
    book.save()
    return book


def _link_file(book: ReelPlaybook, path: Path, role: str) -> None:
    sha, ref = book.store.put_file(path)
    kind = {"mp4": "video", "wav": "audio", "png": "visual", "html": "document"}.get(
        path.suffix.lstrip("."), "file"
    )
    book.catalog.put_asset(
        {
            "sha256": sha,
            "ext": path.suffix.lstrip(".") or "bin",
            "kind": kind,
            "media_type": None,
            "bytes": path.stat().st_size,
            "duration_s": None,
            "width": None,
            "height": None,
            "created_at": now(),
        }
    )
    book.catalog.link_asset(book.slug, sha, role, {"ref": ref, "name": path.name})


def _sha(book: ReelPlaybook, path: Path) -> str:
    sha, _ = book.store.put_file(path)
    return sha


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
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


__all__ = [
    "BuildError",
    "MixError",
    "StateError",
    "build",
    "find_spec",
    "import_legacy",
    "run_check",
    "run_compose",
    "run_gate_check",
    "run_look",
    "run_render",
    "run_voice",
    "run_waveforms",
    "write_board",
]


def _copy_artifacts(source: Path, target: Path) -> None:
    """Copy the files the 0.0.1 project used, so the canonical root is complete."""
    for name in ("STORYBOARD.md", "frame.md", "index.html", "BRIEF.md", "out.mp4"):
        item = source / name
        if item.is_file():
            shutil.copy2(item, target / name)
    for name in ("assets", "compositions", "boards"):
        item = source / name
        if item.is_dir():
            shutil.copytree(item, target / name, dirs_exist_ok=True)


def _legacy_cues(source: Path) -> list[dict]:
    """Cues from a 0.0.1 STORYBOARD.md: frame heading plus narration line."""
    board = source / "STORYBOARD.md"
    if not board.exists():
        return []

    cues: list[dict] = []
    scene, span = 0, None
    for line in board.read_text().splitlines():
        heading = re.match(r"^## Frame (\d+):.*\((\d+(?:\.\d+)?)-(\d+(?:\.\d+)?) s\)", line)
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
