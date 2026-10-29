"""Command line front end. One workspace, slugs, six gates."""

import argparse
import sys
from pathlib import Path

from .book import ReelPlaybook, StateError
from .build import (
    BuildError,
    build,
    store_spec,
    import_project,
    run_check,
    run_compose,
    run_look,
    run_render,
    run_voice,
    run_waveforms,
    stored_spec,
)
from .content import load_spec
from .creative import validate_beats, validate_hooks, validate_idea
from .design import default_frame, parse_frame
from .imagetools import catalogue
from .skills import missing, skill_paths
from .models import VERSION
from .steps import STEPS
from .storage import Workspace

MARKS = {"done": "[x]", "current": "[>]", "failed": "[!]", "locked": "[ ]"}


def _ws(args) -> Workspace:
    return Workspace(args.home, db=args.db)


def _book(args) -> ReelPlaybook:
    return ReelPlaybook.open(
        _ws(args), args.slug, llm_model=getattr(args, "llm_model", None)
    )


def _spec(args):
    return stored_spec(_book(args))


def cmd_init(args) -> int:
    width, height = (int(v) for v in args.size.lower().split("x"))
    book = ReelPlaybook.create(
        _ws(args),
        args.slug,
        fps=args.fps,
        size=(width, height),
        language=args.language,
        max_attempts=args.max_attempts,
        llm_model=args.llm_model,
    )
    print(f"created {book.root}")
    print(f"open: {book.current.name} - {book.current.description}")
    return 0


def cmd_status(args) -> int:
    report = _book(args).status(logs=args.logs)
    flow = report.flow
    print(f"{report.project}  v{report.version}  state {report.state}")
    for step in flow.steps:
        note = f"  {step.evidence}" if step.evidence else ""
        print(f"{MARKS[step.status]} {step.index}. {step.name:<20} {step.status:<8}{note}")
        missing = [path for path, present in step.artifacts.items() if not present]
        if missing:
            print(f"      missing: {', '.join(missing)}")
    print(f"progress {int(flow.progress * 100)}%")
    tokens = ", ".join(f"{k}={v}" for k, v in report.tokens.items() if v is not None)
    print(f"tokens: {tokens}")
    if report.locked:
        print("locked: " + ", ".join(f"{k}@{v}" for k, v in report.locked.items()))
    for entry in report.logs:
        print(f"  {entry.at:%Y-%m-%d %H:%M}  {entry.action:<8} {entry.note or ''}")
    return 0


def cmd_flow(args) -> int:
    flow = _book(args).flow()
    for step in flow.steps:
        print(f"{MARKS[step.status]} {step.index}. {step.name:<20} {step.status}")
    print("next: " + (flow.current.name if flow.current else "done"))
    return 0


def cmd_pass(args) -> int:
    state = _book(args).pass_gate(args.step, args.evidence)
    print(f"passed {args.step} -> {state}")
    return 0


def cmd_fail(args) -> int:
    state = _book(args).fail_gate(args.step, args.reason)
    print(f"failed {args.step}; still at {state}")
    return 0


def cmd_rewind(args) -> int:
    state = _book(args).rewind(args.step, args.reason)
    print(f"rewound to {state}")
    return 0


def cmd_set(args) -> int:
    value = _book(args).set_token(args.key, args.value)
    print(f"{args.key}={value}")
    return 0


def cmd_build(args) -> int:
    book = build(
        _ws(args),
        args.spec,
        whisper_size=args.whisper,
        threads=args.threads,
        render=not args.no_render,
        quality=args.quality,
    )
    print(f"{book.slug}  state {book.state}  {int(book.flow().progress * 100)}%")
    return 0 if book.state == "DONE" else 1 if args.no_render else 0


def cmd_look(args) -> int:
    book = _book(args)
    written = run_look(book, _spec(args))
    for row in written:
        print(f"s{row['index']}  {row['path']}  {row['sha'][:12]}")
    print(f"{len(written)} plates, credits at assets/CREDITS.md")
    return 0


def cmd_voice(args) -> int:
    book = _book(args)
    report = run_voice(
        book, _spec(args), whisper_size=args.whisper, threads=args.threads
    )
    print(
        f"master {report.duration:.3f}s  {report.loudness:.1f} LUFS  "
        f"{report.peak:.1f} dBTP  silence {report.max_silence:.2f}s"
    )
    print(f"{len(book.cues())} cues -> captions.json")
    return 0


def cmd_compose(args) -> int:
    book = _book(args)
    spec = _spec(args)
    run_waveforms(book, spec)
    written = run_compose(book, spec)
    print(f"{len(written)} files, index.html at {book.root / 'index.html'}")
    return 0


def cmd_check(args) -> int:
    book = _book(args)
    print(run_check(book)[-2000:])
    return 0


def cmd_render(args) -> int:
    book = _book(args)
    path = run_render(book, quality=args.quality)
    print(path)
    return 0


def cmd_timeline(args) -> int:
    report = _book(args).timeline(args.video)
    print(
        f"master {report.duration:.3f}s  fps {report.fps:g}  tolerance "
        f"{report.tolerance:.3f}s  cues {report.cues}"
    )
    if report.last_cue_end is not None:
        print(f"last cue ends {report.last_cue_end:.3f}s")
    if report.video_duration is not None:
        print(f"video {report.video_duration:.3f}s at {report.video_fps}fps")
    for warning in report.warnings:
        print(f"warn: {warning}")
    for error in report.errors:
        print(f"FAIL {error}", file=sys.stderr)
    print("ok" if report.ok else f"{len(report.errors)} error(s)")
    return 0 if report.ok else 1


def cmd_list(args) -> int:
    for row in _ws(args).catalog().list_projects():
        print(f"{row['slug']:<32} {row['state']:<6} {row['duration_s'] or '-'}")
    return 0


def _json(path: str):
    import json

    return json.loads(Path(path).read_text())


def _problems(problems: list[str]) -> int:
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    return 1


def cmd_skills(args) -> int:
    step = next((spec for spec in STEPS if args.step in (spec.id, spec.state.lower())), None)
    if step is None:
        print(f"unknown step {args.step!r}", file=sys.stderr)
        return 1
    print(f"{step.index}. {step.name} ({step.id})")
    for label, optional in (("must", False), ("optional", True)):
        for path in skill_paths(step, optional=optional):
            mark = "MISSING" if not path.exists() else ""
            print(f"  {label:<8} {path} {mark}".rstrip())
    if missing(step):
        return 1
    return 0


def cmd_spec(args) -> int:
    book = _book(args)
    if args.file is None:
        print(book.text("spec.json") or "")
        return 0
    spec = load_spec(args.file)
    if spec.slug != book.slug:
        print(f"FAIL spec slug {spec.slug!r} does not match {book.slug!r}", file=sys.stderr)
        return 1
    store_spec(book, spec)
    print(f"spec stored: {len(spec.scenes)} scenes")
    return 0


def cmd_idea(args) -> int:
    book = _book(args)
    if args.file is None:
        import json

        print(json.dumps(book.idea(), indent=2))
        return 0
    record = _json(args.file)
    problems = validate_idea(record)
    if problems:
        return _problems(problems)
    book.put_idea(record)
    print(f"idea stored, score {record['score']}")
    return 0


def cmd_hook(args) -> int:
    book = _book(args)
    if args.file is None:
        import json

        print(json.dumps(book.hooks(), indent=2))
        return 0
    rows = _json(args.file)
    problems = validate_hooks(rows)
    if problems:
        return _problems(problems)
    book.put_hooks(rows)
    print(f"{len(rows)} hooks stored, winner chosen")
    return 0


def cmd_board(args) -> int:
    book = _book(args)
    if args.file is None:
        import json

        print(json.dumps(book.beats(), indent=2))
        return 0
    rows = _json(args.file)
    problems = validate_beats(rows, stored_spec(book))
    if problems:
        return _problems(problems)
    book.put_beats(rows)
    print(f"{len(rows)} beats stored")
    return 0


def cmd_design(args) -> int:
    book = _book(args)
    if args.file is None:
        print(book.text("frame.md") or default_frame(book.design()))
        return 0
    book.put_text("frame.md", Path(args.file).read_text())
    design = parse_frame(book.text("frame.md"))
    print(f"frame.md stored, bg {design.bg}, accent {design.accent}")
    return 0


def cmd_export(args) -> int:
    path = _book(args).export(Path(args.dir))
    print(path)
    return 0


def cmd_import(args) -> int:
    book = import_project(_ws(args), args.path)
    print(f"imported {book.slug}  state {book.state}  {len(book.artifacts())} artifacts")
    return 0


def cmd_catalog(args) -> int:
    for row in _ws(args).catalog().list_projects():
        print(f"{row['slug']:<32} {row['state']:<6} {row['updated_at']}")
    return 0


def cmd_tools(args) -> int:
    for tool in catalogue():
        print(f"{tool['name']:<12} {tool['version']:<8} {tool['class']}")
    return 0


def cmd_specs(args) -> int:
    for step in STEPS:
        print(f"{step.index}. {step.name}  ({step.id} -> {step.state})")
        print(f"   {step.description}")
        print(f"   in:  {', '.join(step.inputs)}")
        print(f"   out: {', '.join(step.outputs)}")
        print(f"   gate: {step.gate}")
        print(f"   owner: {step.owner}")
        if step.locks:
            print(f"   locks on exit: {', '.join(step.locks)}")
        print()
    return 0


def cmd_draft(args) -> int:
    result = _book(args).draft(args.step, args.brief)
    print(result.revised)
    return 0


def cmd_audit(args) -> int:
    from .voice_audit import main as audit_main

    return audit_main(args.files)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reel",
        description="One gated route from an idea to a rendered 9:16 Reel.",
    )
    parser.add_argument("--version", action="version", version=f"reel-playbook {VERSION}")
    parser.add_argument(
        "--home", default=None, help="workspace root (default: $REEL_HOME or ~/Videos/reels)"
    )
    parser.add_argument(
        "--db", default=None, help="database url (default: $REEL_DB or ParadeDB on :5432)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, help_text, *, slug=True, llm=False):
        sp = sub.add_parser(name, help=help_text)
        if slug:
            sp.add_argument("slug")
        sp.set_defaults(func=func)
        if llm:
            sp.add_argument("--llm-model", default=None)
        return sp

    init = add("init", cmd_init, "create a project")
    init.add_argument("--fps", type=int, default=30)
    init.add_argument("--size", default="1080x1920")
    init.add_argument("--language", default="english")
    init.add_argument("--max-attempts", type=int, default=3)
    init.add_argument("--llm-model", default=None)

    status = add("status", cmd_status, "state, flow tracker, tokens, logs", llm=True)
    status.add_argument("--logs", type=int, default=5)

    add("flow", cmd_flow, "step tracker only")
    add("list", cmd_list, "projects in the workspace", slug=False)

    passing = add("pass", cmd_pass, "record a passed gate", llm=True)
    passing.add_argument("step")
    passing.add_argument("--evidence", required=True)

    failing = add("fail", cmd_fail, "record a failed gate", llm=True)
    failing.add_argument("step")
    failing.add_argument("--reason", required=True)

    rewind = add("rewind", cmd_rewind, "reopen a step and drop its gates and locks")
    rewind.add_argument("step")
    rewind.add_argument("--reason", required=True)

    setting = add("set", cmd_set, "set a token (voice, tts_model, duration)")
    setting.add_argument("key")
    setting.add_argument("value")

    skills_cmd = sub.add_parser("skills", help="skills a step must read")
    skills_cmd.add_argument("step")
    skills_cmd.set_defaults(func=cmd_skills)

    spec_cmd = add("spec", cmd_spec, "store or show the scene script")
    spec_cmd.add_argument("--file", default=None)

    for name, func, text in (
        ("idea", cmd_idea, "store or show the idea record"),
        ("hook", cmd_hook, "store or show the hook set"),
        ("board", cmd_board, "store or show the beat plan"),
    ):
        sp = add(name, func, text)
        sp.add_argument("--file", default=None)

    design = add("design", cmd_design, "show or replace frame.md tokens")
    design.add_argument("--file", default=None)

    build_cmd = sub.add_parser("build", help="run all six steps from a content spec")
    build_cmd.add_argument("spec", help="spec path or project slug")
    build_cmd.add_argument("--whisper", default="base.en")
    build_cmd.add_argument("--threads", type=int, default=4)
    build_cmd.add_argument("--quality", default="delivery")
    build_cmd.add_argument("--no-render", action="store_true")
    build_cmd.set_defaults(func=cmd_build)

    for name, func, text in (
        ("look", cmd_look, "render and store the plates"),
        ("voice", cmd_voice, "one master take, align, write cues"),
        ("compose", cmd_compose, "write index.html and compositions from cues"),
    ):
        sp = add(name, func, text)
        sp.add_argument("--spec", default=None)
        if name == "voice":
            sp.add_argument("--whisper", default="base.en")
            sp.add_argument("--threads", type=int, default=4)

    add("check", cmd_check, "hyperframes check")

    drawing = add("render", cmd_render, "hyperframes render to out.mp4")
    drawing.add_argument("--quality", default="delivery")

    timeline = add("timeline", cmd_timeline, "master, cues, composition, render agree")
    timeline.add_argument("--video", default=None)

    exporting = add("export", cmd_export, "write a portable copy of a project")
    exporting.add_argument("dir")

    importing = sub.add_parser("import", help="ingest a project directory")
    importing.add_argument("path")
    importing.set_defaults(func=cmd_import)

    sub.add_parser("catalog", help="projects in the workspace").set_defaults(
        func=cmd_catalog
    )
    sub.add_parser("tools", help="ImageTools").set_defaults(func=cmd_tools)
    sub.add_parser("specs", help="print the six steps").set_defaults(func=cmd_specs)

    draft = add("draft", cmd_draft, "generate, attack and revise a step", llm=True)
    draft.add_argument("step")
    draft.add_argument("--brief", default="")

    audit = sub.add_parser("audit", help="measure a wav (needs the audit extra)")
    audit.add_argument("files", nargs="+")
    audit.set_defaults(func=cmd_audit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (StateError, BuildError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
