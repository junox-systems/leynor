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
uv run reel look 04-five-minutes --spec ~/Videos/reels/specs/04-five-minutes.json
uv run reel voice 04-five-minutes --whisper base.en
uv run reel compose 04-five-minutes
uv run reel check 04-five-minutes
uv run reel render 04-five-minutes
uv run reel timeline 04-five-minutes --video out.mp4

uv run reel tools                     # ImageTools
uv run reel import ~/Videos/reels/01-2009-1969
uv run reel draft 04-five-minutes hook --brief "idea: ..."
uv run reel audit assets/voice.wav     # uv run --extra audit ...
```

## The six steps

| # | Name | Id | Gate | Locks on exit |
|---|------|----|------|----------------|
| 1 | Spark | `idea` | one sentence, HumanKind >= 7, cited input | - |
| 2 | First Three Seconds | `hook` | hook checklist, muted legible | - |
| 3 | Storyboard | `board` | every scene has a visual beat, durations estimated | - |
| 4 | Look | `look` | every scene has a visual, credits complete, 9:16 legible | - |
| 5 | Voice | `voice` | cue drift <= 80 ms, max pause <= 1.2 s, loudness in range | voice, tts_model, duration |
| 6 | Print | `print` | check 0 errors, duration, captions on cue, frames inspected | - |

States: `IDEA -> HOOK -> BOARD -> LOOK -> VOICE -> PRINT -> DONE`.
`pass` moves one state right. `fail` counts to three, then stops the run.
`rewind` reopens a step and deletes every gate and lock at or after it; a rewind
to `voice` or earlier clears the cue map.

## Storage

One workspace, one `reel.sqlite`, content-addressed blobs.

```
~/Videos/reels/
  reel.sqlite          projects, gates, logs, assets, cues, renders
  specs/<slug>.json    content specs, outside the repo
  blobs/ab/cd/<sha>.wav
  projects/<slug>/     manifest.json, assets/, compositions/, index.html, out.mp4
  tmp/                 scratch, deleted after each run
```

Nothing is written outside the workspace (`Workspace.assert_inside`). The
database is authoritative; `projects/<slug>/manifest.json` is the portable
export. The schema is Postgres-safe: TEXT ids, ISO timestamps, `INSERT ... ON
CONFLICT`, no ORM. Moving to Postgres 18 for a Django app means a connection
and a paramstyle, not a rewrite of the model.

## Layout

```
src/reel_playbook/
  steps.py     step catalogue: human name, description, in/out, gate
  models.py    Tokens, GateRecord, Cue, flow tracker, reports
  book.py      ReelPlaybook: FSM, gates, logs, flow, timeline, drafting
  storage.py   Workspace, content-addressed Store, Catalog (SQLite now, Postgres later)
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
