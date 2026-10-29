# Reel Playbook 0.1.0

One gated route from an idea to a rendered 9:16 Reel. Six steps, one state
machine, one workspace, one database. The deliverable is `out.mp4`; publishing
is out of scope.

```python
from reel_playbook import ReelPlaybook, Workspace

book = ReelPlaybook.create(Workspace(), "ep-01")
book.pass_gate("idea", "HumanKind 8; insight cites one competitor post")
book.flow()
book.status().flow.progress
```

Or run the whole pipeline from a committed spec:

```bash
uv run reel build 04-five-minutes
```

## Install

Needs `ffmpeg`, `node` (`npx` for HyperFrames), and Python 3.14 through mise.

```bash
uv sync          # Pocket TTS + CPU torch + faster-whisper, Python 3.14
uv run reel specs
uv run pytest -q
```

## CLI

The workspace defaults to `$REEL_HOME` or `~/Videos/reels`. Pass `--home` to
point somewhere else. Projects are addressed by slug.

```bash
uv run reel init 04-five-minutes
uv run reel list
uv run reel status 04-five-minutes
uv run reel pass 04-five-minutes board --evidence "person: 'go on frame 4'"
uv run reel fail 04-five-minutes hook --reason "no shareable payoff"
uv run reel rewind 04-five-minutes look --reason "palette changed"
uv run reel set 04-five-minutes voice fantine

uv run reel build 04-five-minutes                   # all six steps + render
uv run reel build 04-five-minutes --no-render
uv run reel look 04-five-minutes
uv run reel voice 04-five-minutes --whisper base.en
uv run reel compose 04-five-minutes
uv run reel check 04-five-minutes
uv run reel render 04-five-minutes
uv run reel timeline 04-five-minutes --video out.mp4

uv run reel idea 04-five-minutes --file idea.json
uv run reel hook 04-five-minutes --file hooks.json
uv run reel board 04-five-minutes --file beats.json
uv run reel design 04-five-minutes --file frame.md
uv run reel tools                     # ImageTools
uv run reel import ~/Videos/reels/01-2009-1969
uv run reel export 04-five-minutes /tmp/reel-export
uv run reel draft 04-five-minutes hook --brief "idea: ..."
uv run reel audit assets/voice.wav     # uv run --extra audit ...
```

## The six steps

| # | Name | Id | Gate | Locks on exit |
|---|------|----|------|----------------|
| 1 | Spark | `idea` | score >= 7, insight shape, cited claims, 2 rejected concepts, objection answered | - |
| 2 | First Three Seconds | `hook` | 6+ hooks, 3+ archetypes, one winner, 3-7 word overlay, objection answered | - |
| 3 | Storyboard | `board` | one beat per scene, a turn and a payoff, planned length within 25% | - |
| 4 | Look | `look` | every scene has a visual, credits complete, 9:16 legible | - |
| 5 | Voice | `voice` | cue drift <= 80 ms, max pause <= 1.2 s, loudness in range | voice, tts_model, duration |
| 6 | Print | `print` | check 0 errors, duration, captions on cue, frames inspected | - |

States: `IDEA -> HOOK -> BOARD -> LOOK -> VOICE -> PRINT -> DONE`.
`pass` moves one state right. `fail` counts to three, then stops the run.
`rewind` reopens a step and deletes every gate and lock at or after it; a rewind
to `voice` or earlier clears the cue map.

## Duration

`target_seconds` in the spec sets the cut length: 60-120, default 60. The board
gate fails unless the planned beats land within 15% of it, and unless the script
has at least 80% of the words it needs (about 2.5 words per second, so 150-300
words). Duration is planned, not whatever the takes happen to add up to.

## Creative records

Steps 1-3 are rows, not prose. `reel build` refuses to start without them:

- `ideas`: sentence, insight (`wants X, but Y, because Z`), goal, score,
  citations, rejected alternatives, adversarial objection and answer.
- `hooks`: six or more, three or more archetypes, overlays of 3-7 words, one
  chosen with the objection against it and the answer.
- `beats`: one per scene, first is the hook, one turn, one payoff, overlays
  match the spec, planned length within 25% of the script estimate.

`frame.md` is the look, as input: palette, fonts and caption position live in
its frontmatter and `compose` reads them. Skills are vendored under `skills/`:
`creative-director`, `hyperframes` (plus `-core`, `-animation`, `-keyframes`,
`-registry`, `-cli`, `-creative`), `video-script`, `ig-hook-extractor`,
`ig-audience-insights`, `ig-content-planner`, `ig-hashtag-strategist`,
`ig-humanizer`, `viral-hooks`, `viral-instagram-reels`, `viral-short-form`,
`viral-short-form-ideas`, `viral-youtube-shorts`, `viral-captions-and-ctas`,
`image-visual-skills`, `video-visual-skills`.

## Storage

One workspace on disk, one Postgres database. Everything except `out.mp4` is a
row.

```
~/Videos/reels/
  projects/<slug>/out.mp4    the only kept file
  tmp/                       scratch, deleted after each run
```

Django ORM models in `src/reel_playbook/db/` (`Project`, `Blob`, `Artifact`,
`Gate`, `Log`, `Cue`, `Render`, `CacheKey`). Text artifacts (spec, storyboard,
frame, compositions, captions) are rows; binary ones (visuals, master wav) are
content-addressed blobs referenced by sha256. A render is materialized to a
scratch directory, produced there, and only the mp4 is copied back.

Database URL: `$REEL_DB` or `--db`, default
`postgresql://postgres:postgres@127.0.0.1:5432/reel` (ParadeDB / Postgres 18).
The same models drop into the future Django app unchanged; `migrate` runs on
first use, and `reel export <slug> <dir>` writes a portable copy back to disk.

## Layout

```
src/reel_playbook/
  steps.py     step catalogue: human name, description, in/out, gate
  models.py    Tokens, GateRecord, Cue, flow tracker, reports
  book.py      ReelPlaybook: FSM, gates, logs, flow, timeline, drafting
  storage.py   Workspace, content-addressed Store, Catalog over the ORM
  creative.py  the step 1-3 validators
  design.py    frame.md tokens (input, not output)
  db/          Django ORM models, settings and migrations (postgres only)
  content.py   ReelSpec / SceneSpec, loader
  build.py     the pipeline: spec -> gates -> look -> voice -> compose -> render
  imagetools.py ImageTools: procedural SVG (A), waveform (A+)
  align.py     faster-whisper + sequence match: script text, ASR timing
  voice.py     one master take: trim, two-pass loudnorm, measure
  compose.py   HyperFrames HTML from cues and visuals
  timeline.py  master / cue / data-duration / mp4 agreement
  graphs.py    pydantic-graph draft loop: generate -> critique -> revise
  agents.py    pydantic-ai agents behind that graph
  tts.py       Pocket TTS 100M (`english`) in-process on CPU
  cli.py       `reel` commands
tests/         storage, FSM, locks, rewind, alignment, composition, timeline
```

## Voice

Pocket TTS 100M (`--language english`, 24 kHz mono). The model id is recorded in
the database and locked when step 5 closes, because a model swap moves the voice
by semitones (100M `fantine` sits 1.4 semitones below 18M).

One continuous take per episode, not one file per scene. The master is trimmed
at both ends, normalized once to -14 LUFS / -1.5 dBTP in stereo, and written to
`assets/voice.wav`. Cues come from `faster-whisper base.en`: ASR supplies
timings, the known script supplies the text. `captions.json` is the cue map and
the clock for every scene. `reel audit` needs the `audit` extra (librosa).
