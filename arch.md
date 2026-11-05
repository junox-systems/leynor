# Reel Playbook — Architecture

How the six steps in `playbook.md` are implemented. The playbook owns order,
gates and artifacts; this file owns storage, commands, host state and measured
numbers. If they disagree about a command, this file wins; about a gate, the
playbook wins.

Version: **0.1.0**. The `LOOK/VOICE/PRINT` states, the single workspace, the
content-addressed store and the one-master voice pipeline are coded and tested;
`reel build content/<slug>.json` runs all six steps end to end. Reels 04-06 in
`~/Videos/reels` are the first builds on this code.

## Host inventory

Verified 2026-10-23.

| Need | State | Fix if missing |
|---|---|---|
| Node | v26.8.2 | ok |
| FFmpeg / ffprobe | n9.0.2 (libass, drawtext) | ok |
| HyperFrames CLI | 0.8.188 via `npx` | `npx hyperframes upgrade` |
| Chrome headless shell | installed | `npx hyperframes browser ensure` |
| Docker | 29.9.1, running | container render fallback |
| Python | 3.14.8 (mise), pinned in `.python-version`; package needs >= 3.14 | torch/faster-whisper wheels resolve on 3.14 |
| uv | 0.12.19 | `uv sync` installs the package and TTS |
| Postgres | 18.6, ParadeDB 0.26.2, `127.0.0.1:5432`, db `reel` | `docker start <paradedb>`; `REEL_DB` overrides |
| `reel` package | 0.1.0, uv-managed | `uv sync` |
| Pocket TTS | 4.0.1, 100M weights, base dependency | `uv sync` |
| torch | 2.14.1+cpu, from the CPU index | never the CUDA wheels |
| mpv | 0.41.0 | previewing the master wav |
| CPU / RAM | 4 cores / 15 GB, no CUDA | CPU-only paths everywhere |
| `APIFY_TOKEN` | unset | step 1 read is manual paste |

TTS is local. No heygen, no hosted TTS, no API key.

## Storage: one workspace, one database

The builder writes only inside `REEL_HOME`. `/tmp` is forbidden; a test asserts
every written path resolves under the root. `REEL_HOME` is `~/Videos/reels`
today and the app data directory later.

Everything except the render is a row in Postgres 18. The filesystem keeps one
file per project:

```
$REEL_HOME/
  projects/<slug>/out.mp4   # the deliverable, nothing else
  tmp/<job>/                # artifacts materialized for render, wiped after
```

`REEL_DB` selects the database; default is ParadeDB 0.26.2 (PG 18.6) on
`127.0.0.1:5432`, database `reel`, user/password `postgres`. SQLite is gone: one
backend, one dialect, no dual-path tests.

The ORM is Django's, in `src/reel_playbook/db/`. Same models the web app will
import; `migrate` runs on first `Catalog` use.

```python
Project(slug PK, state, version, root, fps, width, height, duration_s,
        max_attempts, tokens_json, locked_json, created_at, updated_at)
Blob(sha256 PK, ext, kind, media_type, bytes, data bytea, created_at)
Artifact(slug, path, kind, text, sha256, meta_json, created_at,
         PK(slug, path))
CacheKey(key PK, sha256, tool, tool_version, created_at)
Gate(slug, step, result, attempts, evidence, at, PK(slug, step))
Log(id PK, slug, at, action, from_state, to_state, note)
Cue(slug, idx, scene, start_s, end_s, text, PK(slug, idx))
Render(id PK, slug, sha256, duration_s, fps, loudness, peak, verified_at)
Idea(slug PK, sentence, insight, goal, score, citations_json,
     alternatives_json, adversarial_json, created_at)
Hook(slug, idx, archetype, spoken, first_frame, overlay, chosen,
     objection, answer, PK(slug, idx))
Beat(slug, idx, name, purpose, overlay, visual_beat, seconds_est,
     PK(slug, idx))
```

Steps 1-3 are validated from `ideas`, `hooks`, `beats`, never from the spec.
`creative.py` owns the rules; a failing record stops `build` before any audio.
`frame.md` frontmatter is the design input (`design.py`), read by `compose`.

Two hashes, deliberately different:

- **key** = `sha256(tool, tool_version, params, inputs)` -> cache lookup.
- **blob** = `sha256(bytes)` -> dedupe and immutable identity.

Same voice line across 200k projects is one blob. Same prose with a new voice is
a new blob under the same tool.

Artifacts are either text (spec, storyboard, frame, compositions, captions) or a
blob reference (visuals, master wav). `book.materialize(dir)` writes the tree for
HyperFrames; the render happens in `tmp/`, and only `out.mp4` is copied back.
`book.export(dir)` writes a portable copy including `manifest.json`.

## Component map

| Component | Step | In | Out |
|---|---|---|---|
| C1 spark | 1 | niche, person, goal | idea, insight, primary goal |
| C2 hook | 2 | idea, goal | winning hook (verbal, frame 1, overlay) |
| C3 storyboard | 3 | hook, goal | `STORYBOARD.md` with visual beats, `boards/` |
| C4 look | 4 | storyboard, tone | `frame.md`, visual assets, credits |
| C5 voice | 5 | script, voice tokens | `voice.wav`, `captions.json`, mix |
| C6 print | 6 | visuals, cue map, master | `out.mp4` |

## Mechanical checks

| Command | Answers | Fails on |
|---|---|---|
| `reel status` / `pass` / `fail` / `rewind` | which step is open, what is locked, which gate passed | illegal transition, locked token change, fourth attempt |
| `reel timeline` | does the master, cue map and render agree | gap, overlap, drift over one frame, caption drift over 80 ms |
| `reel captions` | is every spoken word covered by a cue | uncovered word, cue over 6 s, over 2 lines |
| `uv run pytest -q` | does the FSM, store and timeline still work | any regression |

## C1 — spark

Owning skill: `creative-director`, phases 1-4 only.

- Phase 1: `idea_type: execution`.
- Phase 2: `audience wants X, but Y stands in the way, because Z`.
- Phase 3: 3 method categories, 8-12 one-line ideas, first 3 as warmup.
- Phase 4: six weighted criteria plus HumanKind, keep the top one.

Optional data read: `ig-audience-insights` needs `APIFY_TOKEN` (unset). Fallback:
paste 2-3 competitor posts into `ig-hook-extractor`.

Out contract: one sentence, one cited input, HumanKind >= 7, one primary goal
(`saves` / `shares` / `follows`) that the hook promises.

## C2 — hook

Owning skills: `viral-hooks`, plus `viral-instagram-reels` ->
`references/reels-hook.md` for timing and muted legibility.

Out contract: verbal line, first frame, overlay text (3-7 words), passing
`viral-hooks` -> `assets/hook-checklist.md`.

## C3 — storyboard

`ReelSpec.target_seconds` (60-180) is the cut length. The board gate checks the
planned beats against it (15%) and the script word count against the spoken
budget (2.5 words/s, 80% floor), so a 20 s script cannot pass as a 60 s reel.


Owning skills: `viral-instagram-reels` -> `assets/reels-script-template.md`,
`video-script` (65-160 words for 30-60s, 130-160 wpm), `hyperframes` ->
`references/storyboard-format.md`.

`STORYBOARD.md`, one section per scene:

```markdown
## Frame 1: name (0-3.2 s) est
- narration: <verbatim spoken line>
- on-screen: <text>
- visual: ImageTools tool A/A+ and the beat
- audio: <intent; no file yet>
```

Durations are estimates from word count. The voice is the clock: step 5 replaces
`est` with cue-derived boundaries. Numbers in narration are spoken-form.

Out contract: scene list with narration, overlay, visual beat; board rendered for
review. No audio exists at this point.

## C4 — look

Owning skills: `hyperframes-creative` (`house-style.md`,
`video-composition.md`, then `visual-styles.md` or a palette).

ImageTools is the only source of visuals. One interface, versioned backends:

```python
class ImageTools(Protocol):
    name: str
    version: str
    def render(self, scene: Scene, seed: int, audio: AudioSpan | None) -> list[AssetRef]: ...
```

| Tool | Output | Notes |
|---|---|---|
| A `procedural` | deterministic SVG/PNG: grain, halftone, grid, rules | default; no license |
| A+ `waveform` | `ffmpeg showwavespic` strip, optional spectrogram, per cue | needs the master, so it runs after C5 |
| B `stock` / `ai` | later, same interface | needs a license row and a key |

`frame.md` carries colors, fonts, spacing, tone, `pronounce:`. Tool, version,
seed and params are part of the cache key. Every asset gets a row in
`assets/CREDITS.md`.

Out contract: every scene has at least one visual asset, credits complete,
9:16 contrast and legibility pass.

## C5 — voice

One continuous take per episode. Pocket TTS 100M, in-process, installed by uv:

```python
book.speak_master(script)        # target API
uv run reel voice <project>      # target CLI
```

- Model ids are the library's `language` values: `english` is 100M;
  `english_18m_2026-10` and friends are faster and flatter. One model per
  series: `alba` drops 3.5 semitones and `fantine` 1.4 from 18M to 100M.
- Predefined voices: `alba`, `anna`, `azelma`, `bill_boerst`, `caro_davy`,
  `charles`, `cosette`, `daan`, `eponine`, `estelle`, `eve`, `fantine`,
  `george`, `giovanni`, `jane`, `javert`, `jean`, `juergen`, `lola`, `marius`,
  `mary`, `michael`, `paul`, `peter_yearsley`, `rafael`, `stuart_bell`, `vera`.
- Output is 24 kHz mono s16; the file writer is stdlib `wave`.
- Measured: 21 s cold start including model load for one short command, then
  ~2 s per line. Load once; never one process per scene.
- Takes are cached per scene by key and can be re-synthesized alone, but the
  master is always one file. Joins are 120-180 ms and only for edit mode.

### Alignment (captions and the clock)

We know the words, so this is alignment, not transcription. Backends behind one
interface:

| Backend | Shape | Status |
|---|---|---|
| `faster_whisper` `base.en` int8, `beam_size=1`, `word_timestamps=True` | default, CPU | measured RTF 0.13 |
| `torchaudio` MMS_FA forced alignment | faster, exact with known text | not needed yet |

Steps: ASR on the master, edit-distance correction against the script, keep ASR
timings with script text, write `captions.json`. One pass per master. Audio is
decoded by ffmpeg to 16 kHz float32 and passed as an array: PyAV 19 dropped the
`metadata_errors` argument faster-whisper still passes. Cue starts are clamped
to the previous cue end so ADJACENT sentences never overlap. Gate is RTF < 0.5
on 4 cores; measured 3.27 s for a 24.5 s master (0.13).

### Mix

- Trim leading and trailing silence.
- No pad-to-scene: the old `apad -t` recipe made the duration check tautological
  and hid clipped words; it is gone.
- Loudness: two-pass `loudnorm` on the wav, -14 LUFS integrated (within
  0.5 dB), peak <= -1.5 dBTP, then
  write the master. Never re-encode the rendered mp4.
- The master is 48 kHz stereo. A mono master encoded into a stereo AAC track
  reads 3 dB louder than its own wav, so normalising stereo keeps the mp4 at
  -14 LUFS. Measured on reels 04-06: -14.0 LUFS / -1.5 dBTP in both the master
  and the mp4.
- Gates: cue drift <= 80 ms, max pause <= 1.2 s, no clipped
  samples, person listens once.

Out contract: `assets/voice.wav`, `captions.json`, duration and cue hash locked.

## C6 — print

Owning skills: `hyperframes`, `hyperframes-core`, `hyperframes-animation`,
`hyperframes-keyframes`, `hyperframes-registry`, `hyperframes-cli`.

```bash
npx hyperframes usage --json
npx hyperframes check
npx hyperframes snapshot --review
npx hyperframes render --quality delivery --output out.mp4
uv run reel timeline <project> --video out.mp4
```

- One scene per sub-composition mounted with `data-composition-src`; ids match
  the host slot and the timeline key.
- Root `data-duration` equals the master duration; fps 30.
- One caption track, one timed element per cue from `captions.json`.
- `assets/voice.wav` is mounted once. No per-scene audio, no post-render trim.
- `check` must report 0 errors and non-zero audit sample counts. A lint error
  switches the layout and contrast audits off and reports `0/0`, which reads
  clean and means nothing ran.
- Measured on this host: 35.9 s, 1080x1920, `--quality delivery`, 1077 frames in
  69.5 s (`beginframe`, hardware GPU). 31.2 s in 60.4 s. Budget ~2x realtime.
- Verify: master duration and fps, loudness on the master, captions on their
  cues, decoded frames at key seconds.

Out contract: `out.mp4` at 1080x1920, 30 fps, duration within one frame of the
master, all gates recorded.

## Invariants

- One workspace root; no asset outside it; scratch under `tmp/`.
- One database for all projects; the manifest is the portable export.
- One master wav per episode; cues, not per-scene audio files.
- Every asset is a blob with a cache key, a license row, and a reproducible
  tool/version/seed.
- Root `data-duration` == master duration == rendered duration, within one frame.
- Loudness is fixed on the master, never on the rendered file.
- One voice model and one voice per series, locked at step 5.
- An artifact without a gate record is not a passed step.

## Known gaps

- Reels 01-03 predate the master-wav pipeline: they were imported from 0.0.1
  (per-scene wavs, `STATE.json`) into the one DB, so they have cues and assets
  but no `assets/voice.wav`. `reel timeline` is meaningful for 04-06 only.
- The ASR gate text says RTF < 0.5; measured 0.13 for `base.en` int8 on 4 cores.
- Tests run against a real Postgres (`reel_test`), not a mock: they need the
  ParadeDB container up, or `REEL_DB` pointing at another PG 18.
- Reels 01-03 predate the creative tables: their `ideas`, `hooks` and `beats`
  are empty, so `reel build` refuses to rebuild them without seeding records.
- The records for 04-06 were seeded after those reels were already rendered;
  they validate now, but they were not the gate that produced the original edit.
- A+ waveform needs the master, so it runs after C5 while A runs in C4. The
  composer already accepts late-bound visuals via the extra plate slot.
- The IG skills cite `../../references/hook-formulas.md`,
  `hashtag-strategy.md`, `media-workflow.md`, `algorithm-heuristics.md`. None
  are vendored.
- `APIFY_TOKEN` unset: step 1 cites pasted competitor posts instead of live data.
