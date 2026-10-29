# PLAN: Reel Playbook as a private Django app

Status: phases 0 to 2 done on branch `feat/django-app`. Phases 3 to 8 are
still plan only.

Verified so far:
- heavy image builds and renders a 3.000s 1080x1920 clip inside the container
  (torch 2.15.0+cpu, faster-whisper, pocket-tts, ffmpeg 7.1.5, Chromium 156,
  HyperFrames 0.8.188).
- dev stack boots: `/healthz/` 200, `/` redirects to login, `/accounts/login/`
  200, `/dashboard/` 200, admin 200, qcluster runs as cluster `reel-default`.
- 275 tests pass, 1 skipped; ruff clean. Only pyflakes-level rules are enabled.
- the engine package, its `db/` shim, the CLI and `build()` are deleted.

Still open from the earlier drafts:
- `async_task(..., cluster="heavy")` is not exercised yet (phase 4). The queue
  name is set by env, verified in the default worker's log line.
- no models exist yet, so nothing writes a `Run` row.


Base: `/home/hanz/Projects/experiments/leynor` (Django 5.2 starter kit). The
first draft named `/home/hanz/Projects/django-starter-kit`; that path does not
exist. leynor is the same kit, already forked.

Engine source: `src/reel_playbook` (4,351 lines, 979 lines of tests). It is not
a library to keep. It is the playbook's behaviour, and it moves into the app.

## Goal

Turn the CLI pipeline into a private, self-hosted Django app for personal or
small-team use. No billing, no subscriptions, no quotas. Local filesystem
storage now, S3 later. One host, one database, one artifact store.

## No separate package

The old draft put the domain in `pipeline/`, a plain package outside Django.
That is wrong for this project:

- It splits one bounded context in two. The playbook's invariants (gate order,
  one active run, immutable spec) would live outside the models that own them.
- It doubles the wiring: repository ports, adapters, and a second set of tests
  for code that only ever has one caller.
- The app is the playbook. The playbook is not a dependency of the app.

Everything is an app. The only real boundary the old draft was reaching for is
"do not load torch or Chromium in the web container". That is a dependency
boundary, solved by lazy imports and an optional dependency group, not by
package placement.

## DDD analysis

### Bounded contexts

| Context | Kind | Owns | Does not own |
|---|---|---|---|
| `projects` | core domain | the six steps, gate policy, spec versions, project log | execution, media |
| `runs` | supporting | one execution: run, step runs, artifacts, resume, cancel | creative decisions, rendering |
| `creative` | core domain | idea, hook, beat; drafting agents; validation rules | files, audio, video |
| `voices` | supporting | cue map, TTS, ASR, mix | visuals, gate policy |
| `renders` | supporting | design, frames, composition, timeline, video encode | audio generation, gate policy |

`orgs`, `users`, `core`, `api`, `dashboard`, `pages` are leynor's, unchanged.

Why steps are not contexts: `idea`, `hook`, `board`, `look`, `voice`, `print`
are stages of one process, not separate languages. They share the `Project`
aggregate and one `Spec`. Six apps would be six folders with one file each and a
cycle in every direction.

### Aggregates and invariants

| Aggregate root | Members | Invariants enforced on the model |
|---|---|---|
| `Project` | `Spec`, `Gate`, `Log` | at most one `Spec` per version and versions are immutable; a gate passes only in step order; board and print need a human approver; `next_step` is derived, never assigned |
| `Run` | `StepRun`, `Artifact` | one live run per project (partial unique index); a step run starts only when the previous step succeeded; artifacts are scoped to one run and one path; only a terminal run frees the project |

Cross-aggregate rules live in one application service, `runs/services/run.py`.
Nothing else moves both aggregates in one transaction.

### Context map

```
projects  <--  runs  -->  creative
                  |
                  +-->  voices
                  |
                  +-->  renders
```

- Arrows are imports, one way only. `runs` imports the other three. The other
  three never import `runs`.
- Shared kernel: `projects/spec.py` (`Spec`, `Tokens`, `Step`) and
  `voices/cues.py` (`CueData`). Value objects are pydantic models, not ORM rows,
  so `renders` can take cues without touching `voices` tables.
- Anti-corruption: `src/reel_playbook/db/` is deleted, not adapted. The old
  free-text `state`, `tokens_json`, and `Blob` do not survive.
- No domain events in v1. `Log` rows already answer "what happened" for one
  project, and q2 already retries.

## SOLID analysis

| Principle | Today (measured) | After |
|---|---|---|
| SRP | `book.py` (577 lines) is FSM, repository, agent cache, exporter, and disk writer; `build.py` (634 lines) is all six steps | `Project` holds invariants; `RunProject` holds orchestration; each step is a function in the app that owns it; `Store` holds files; `tasks.py` holds queue ingress |
| OCP | adding or reordering a step means editing `build()` and `steps.py` | a step is a `Step` member plus an entry in `runs/registry.py`; the orchestrator loop does not change |
| LSP | `Workspace`, `Store`, `Catalog` overlap and disagree on who owns bytes | one `Store` contract: `put` returns sha256, `get` raises `ArtifactMissing`, `tmpdir` context manager. `FileStore` now, `S3Store` later, same contract |
| ISP | four store ports force every caller to know all of them | `Store` has three methods; the renderer takes `(compose_dir, out_path, quality)` and nothing else; drafting takes `(step, brief)` and returns text |
| DIP | `book.py` news up `Catalog` and `build_agents`; `build.py` shells out to `npx` inline | high-level policy (`RunProject`, gate rules) depends on callables from `registry.py`; tests inject fakes; ffmpeg and Chromium sit in `renders` behind one function each |

Second rule of the analysis: `runs` must not import `voices.tts` at module
level. It resolves the step runner from `registry.py` inside the function, so
the web process never imports torch.

## Lazy heavy imports

The web container must not carry torch, faster-whisper, pocket-tts, Node, or
Chromium. Enforced in three places:

1. `pyproject.toml`: heavy packages are an extra, not base dependencies.
   `uv sync` gives the web image; `uv sync --extra heavy` gives the worker.
2. Module-level imports of `torch`, `faster_whisper`, `pocket_tts` appear only
   in `voices/tts.py`, `voices/asr.py`, and `renders/video.py`, and only inside
   function bodies. `renders/video.py` launches ffmpeg and HyperFrames with
   `subprocess`, so it needs no import at all.
3. `tests/test_web_boot.py` imports `config.urls` and asserts `torch` and
   `faster_whisper` are absent from `sys.modules`. That test is the boundary.

Settings never import a media module. `REEL_LLM_MODEL`, `REEL_WHISPER_SIZE`,
`REEL_ARTIFACT_ROOT`, and `REEL_RENDER_QUALITY` are plain values.

## Target layout

```
apps/
  projects/
    models.py            Project, Spec, Gate, Log
    gates.py             Step, GateResult, HUMAN_GATES, order rules
    spec.py              Spec, Tokens, load and validate
    steps.py             step catalogue: names, inputs, outputs, skills, prompts
    services.py          create project, new spec version, approve, reject
    panels.py            project summary payload
    views.py urls.py forms.py admin.py
    tests/
  runs/
    models.py            Run, StepRun, Artifact
    artifacts.py         Store protocol, FileStore, artifact keys, path guards
    registry.py          step id -> runner callable
    services/run.py      RunProject: create, execute, resume, cancel
    services/state.py    run_state(run) payload, the only UI contract
    tasks.py             q2 ingress: execute, heartbeat, sweep
    views.py urls.py panels.py admin.py
    tests/
  creative/
    models.py            Idea, Hook, Beat
    validators.py        idea, hook, beat rules
    agents.py            pydantic-ai drafter, critic, reviser
    graphs.py            pydantic-graph generate, critique, revise
    skills.py            step skill docs into the drafter prompt
    services.py          draft(step, brief) -> DraftResult
    tests/
  voices/
    models.py            Cue
    cues.py              CueData value object
    tts.py               pocket-tts, lazy
    asr.py               faster-whisper, lazy
    mix.py               one master take, loudness
    services.py          run_voice(spec, store) -> VoiceResult
    tests/
  renders/
    design.py            frame, palette, typography
    media.py             procedural and waveform visuals
    compose.py           HyperFrames HTML
    timeline.py          duration, fps, loudness checks
    video.py             ffmpeg and HyperFrames subprocess
    services.py          run_look, run_compose, run_print
    tests/
  core/ users/ orgs/ pages/ dashboard/ api/
config/ templates/ frontend/
```

Delete: `src/reel_playbook/db/` (its schema is replaced by app models),
`src/reel_playbook/cli.py` (478 lines), `storage.py` (364 lines, split into
`runs/artifacts.py` and the app models), `book.py` (577 lines, split as above),
`build.py` (634 lines, split into per-step services under `runs/services` and
each owning app).

What moves where:

| Engine file | Destination |
|---|---|
| `steps.py` | `projects/steps.py` |
| `content.py` | `projects/spec.py` |
| `models.py` (`Cue`, reports) | `voices/cues.py`, `renders/timeline.py` |
| `book.py` | `projects/models.py`, `projects/gates.py`, `runs/services/*` |
| `storage.py` | `runs/artifacts.py`, `runs/models.py` |
| `creative.py` | `creative/validators.py` |
| `agents.py`, `graphs.py`, `skills.py` | `creative/` |
| `voice.py`, `tts.py`, `align.py`, `voice_audit.py` | `voices/` |
| `design.py`, `imagetools.py` | `renders/` |
| `compose.py`, `timeline.py` | `renders/` |
| `build.py` `run_render`, `run_check` | `renders/video.py`, `renders/services.py` |
| `cli.py` | deleted |
| `tests/` | split per app; golden snapshots kept |

## State model: one vocabulary

```python
# apps/projects/gates.py
class Step(models.TextChoices):
    IDEA = "idea", "Spark"
    HOOK = "hook", "Hook"
    BOARD = "board", "Board"
    LOOK = "look", "Look"
    VOICE = "voice", "Voice"
    PRINT = "print", "Print"

HUMAN_GATES = {Step.BOARD, Step.PRINT}

class GateResult(models.TextChoices):
    PENDING = "pending"
    AUTO = "auto"
    APPROVED = "approved"
    REJECTED = "rejected"

# apps/runs/models.py
class RunStatus(models.TextChoices):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DONE = "done"

class StepStatus(models.TextChoices):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
```

Rules:

- No stored `Project.state`. The cursor is the first step whose latest
  `StepRun` is not `succeeded`. `Project.next_step` is a property.
- No uppercase mirror of the step list. `Step` definition order is the route
  order; `projects/steps.py` indexes by `Step.value`.
- One function produces everything the UI shows:
  `runs/services/state.py: run_state(run) -> dict`. The Cotton tracker, the htmx
  partial, and any future JSON endpoint consume that dict. A test asserts both
  render from it.
- Labels live in the payload, never in JS or a second template constant.

## Data model

All roots inherit `core.BaseModel` and carry `organization`. `auditlog` on
`Project`, `Spec`, `Gate`, `Run`.

| Model | App | Fields and constraints |
|---|---|---|
| `Project` | projects | org, slug, title; unique `(org, slug)` |
| `Spec` | projects | project, version, payload JSONField; immutable |
| `Gate` | projects | project, step, result, attempts, evidence, kind, approved_by, approved_at; unique `(project, step)` |
| `Log` | projects | project, run, action, from_step, to_step, note |
| `Run` | runs | org, project, status, spec_version, heartbeat_at, started_at, ended_at, meta_json; partial unique `(project)` where status in queued, running, waiting_review |
| `StepRun` | runs | run, step, attempt, status, error, started_at, ended_at, meta_json; unique `(run, step, attempt)` |
| `Artifact` | runs | project, run, path, kind, text, file, sha256, bytes, meta_json; unique `(run, path)` |
| `Idea` / `Hook` / `Beat` | creative | project, payload fields |
| `Cue` | voices | run, idx, scene, start_s, end_s, text; unique `(run, idx)` |

Dropped from the current schema: `Blob` (bytes move to disk), `Render` (timeline
report, loudness, fps go to `StepRun.meta_json`), `CacheKey` (compose cache is
not in v1; measure in phase 7). No `Plan`, `Subscription`, `Entitlement`,
`UsageLedger`, `VoiceMaster`.

## Orchestration: one run task, two workers

```
default  2 workers, timeout 1500   leynor's mail and housekeeping
heavy    1 worker,  timeout 3600   apps.runs.tasks.execute only
```

Cluster settings come from env in the same `Q_CLUSTER` dict
(`Q_CLUSTER_NAME`, `Q_CLUSTER_WORKERS`, `Q_CLUSTER_TIMEOUT`,
`Q_CLUSTER_RETRY`), each container running `qcluster` with its own values.
`async_task(..., cluster="heavy")` is the dispatch side. This avoids depending
on `ALT_CLUSTERS`, which is not installed in either tree to verify.

Why one task for the whole run instead of one task per step: resumption needs
`StepRun` rows anyway, so the task reads them and continues from the first
unsucceeded step. One task means one place implements resume, cancel, and gate
waiting. Steps 1 to 4 are seconds of work and can share the heavy worker.

```
POST /projects/<slug>/runs/
  reject if an active run exists (partial unique index, not check-then-insert)
  create Run(queued) and six StepRun rows
  transaction.on_commit -> async_task("apps.runs.tasks.execute", run_id, cluster="heavy")

tasks.execute(run_id):
  advisory lock pg_try_advisory_lock(project_id); exit if held
  for each step from the first unsucceeded:
    mark RUNNING, write heartbeat
    runner = registry.runner(step)            # resolved inside the function
    result = runner(project, spec, store)     # lazy heavy imports live behind it
    save Artifact rows, pass gate with evidence, or stop
    HUMAN gate: Run WAITING_REVIEW, return cleanly
    failure: StepRun FAILED, Run FAILED, stop
  all succeeded -> Run DONE
```

- Cancel: `Run.cancel_requested_at`, checked before each step and passed to the
  renderer to kill the process tree.
- Sweeper: q2 schedule every 5 minutes, re-enqueues `queued` runs with no task,
  fails `running` runs whose heartbeat is older than 10 minutes.
- Retry: `retry` above `timeout`, `max_attempts=1`. Adapter retries only for
  subprocess flake, with backoff, inside the step.
- Resumption is idempotent: artifacts are `update_or_create` on `(run, path)`;
  the render writes a temp file then renames.

## LLM drafting: pydantic-ai and pydantic-graph

Kept as is, moved into `creative/`:

- `agents.py` builds three pydantic-ai agents with `defer_model_check=True`, so
  import needs no key and no network.
- `graphs.py` is the deterministic generate, critique, revise graph with
  `DraftDeps` injected. Tests run it with plain callables, no model.
- `skills.py` loads the step's skill docs into the drafter prompt.

Changes for the app:

- The model string comes from `settings.REEL_LLM_MODEL` and is passed into
  `build_agents(model=...)`. No env reads inside the app modules.
- Drafting runs inside the run task, called through `creative/services.py`.
  Result is saved as `Artifact` text and as the step's creative row. No agent
  touches the ORM.
- The six-step route stays a database state machine. Do not encode it as a
  pydantic graph: it spans human approvals and days, and the DB is the durable
  log. pydantic-graph is for the LLM loop only, one graph for steps 1 to 3,
  parameterized by `Step`.

## Artifacts

```
var/artifacts/<org_uuid>/<project_uuid>/<run_uuid>/<path>
media/            avatars only, public
```

- `Artifact.file` uses `artifact_storage` (`FileSystemStorage` rooted at
  `var/artifacts`). Small text stays in `Artifact.text`.
- `sha256`, bytes, kind, and metadata live on the row.
- No public `MEDIA_URL` for artifacts. Download is an authenticated view that
  checks `rbac.check_access(request, "runs.view_artifact", artifact)`.
- Reject `..` and absolute paths at write and read.
- `Store` contract: `put` returns sha256, `get` raises `ArtifactMissing`,
  `tmpdir` is a context manager. Disk now; S3 later swaps one class.
- No blob dedupe in v1.

## UI

| Route | What it is |
|---|---|
| `/projects/` | Cotton table: title, last run status, updated |
| `/projects/new/` | Django form: title, slug, niche, goal |
| `/projects/<slug>/` | tracker, spec, creative edits, artifacts, runs, approve, cancel |
| `/projects/<slug>/runs/<id>/state/` | htmx partial from `run_state`, polled every 2s while live |
| `/artifacts/<id>/` | authenticated download, `FileResponse` in dev, `X-Accel-Redirect` in prod |
| `/runs/<id>/cancel/`, `/projects/<slug>/gates/<step>/approve/` | plain POST forms |

- Tracker is `<c-step-tracker :payload>`, server-rendered. Polling stops when the
  run is terminal, signalled by `HX-Trigger`, so no Stimulus controller and no
  Svelte island is needed for v1.
- No DMR endpoints for runs. `apps/api` keeps leynor's user and activity
  endpoints. A second JSON contract is what let the first draft drift.
- Spec editing is a JSON textarea validated by `projects/spec.py`, pydantic
  errors rendered as form errors. Per-field forms later if it hurts.
- Every authed page extends `base_app.html`.

## Tenancy and permissions

Keep `Organization`, `Membership`, `Role`, `rbac.check_access`. Add to
`Organization.Meta.permissions`, granted to owner and admin:

- `run_project`
- `approve_gate`
- `view_artifact`

Every query org-scoped through the model's `organization` FK. Cross-org tests
for every view and every task.

## Runtime

```
web                 Granian, web image: no torch, no Node, no Chromium
qcluster-default    leynor tasks, timeout 1500
qcluster-heavy      apps.runs.tasks.execute, 1 worker, timeout 3600
postgres            ParadeDB image from leynor
nginx               TLS and X-Accel-Redirect in production
```

Images: `web` syncs base dependencies only. `heavy` syncs `--extra heavy` and
adds ffmpeg, Node, Chromium, HyperFrames, all pinned.

Render sandbox: non-root, read-only root, scratch tmp, artifact mount only, no
egress, memory and time limits, killed on cancel.

Split `heavy` into `media` and `render` only after phase 7 measures headroom.

## leynor wiring (exact deltas)

Final tree, leynor files plus the five apps:

```
apps/
  projects/
    apps.py models.py gates.py spec.py steps.py services.py panels.py
    forms.py views.py urls.py admin.py migrations/ tests/
  runs/
    apps.py models.py artifacts.py registry.py
    services/run.py services/state.py tasks.py
    views.py urls.py panels.py admin.py migrations/ tests/
  creative/
    apps.py models.py validators.py agents.py graphs.py skills.py
    services.py admin.py migrations/ tests/
  voices/
    apps.py models.py cues.py tts.py asr.py mix.py services.py
    admin.py migrations/ tests/
  renders/
    apps.py design.py media.py compose.py timeline.py video.py services.py tests/
  core/ users/ orgs/ pages/ dashboard/ api/      (leynor, pages trimmed)
config/settings/{base,dev,production,test}.py
templates/projects/  templates/runs/  templates/cotton/step_tracker.html
var/artifacts/  media/
tests/test_web_boot.py  tests/test_layering.py
```

`renders` ships no models. That is legal and deliberate: it is a context with
behaviour (design, compose, timeline, encode) and no persisted state of its own.

| File | Change |
|---|---|
| `config/settings/base.py` `INSTALLED_APPS` | add the five apps after `apps.users`, before `apps.api` |
| `config/settings/base.py` | new `REEL_*` block and env-driven `Q_CLUSTER` |
| `config/urls.py` | add `projects/` and `runs/` includes, drop the sitemap path |
| `apps/pages/views.py` | `home` becomes a redirect: dashboard when authed, login otherwise |
| `apps/pages/urls.py` | keep `robots.txt` only; delete terms, privacy, sitemap |
| `apps/runs/artifacts.py` | `artifact_storage()` returns the local or S3 backend |
| `apps/runs/models.py` | `Artifact.file = FileField(storage=artifact_storage(), upload_to=artifact_path)` |
| `apps/orgs/models.py` `Organization.Meta.permissions` | add `run_project`, `approve_gate`, `view_artifact` |
| `apps/orgs/migrations/0003_reel_permissions.py` | grant the three to the admin default role |
| `pyproject.toml` | rename to `reel-playbook`; base deps `pydantic`, `pydantic-ai`; `heavy` extra; delete `[project.scripts]` |
| `mise.toml`, `frontend/package.json`, `README.md`, `.env.example` | rename and add the REEL keys |
| `dev/Dockerfile.heavy` | new: ffmpeg, Node, Chromium, HyperFrames, torch CPU, faster-whisper, pocket-tts |
| `dev/docker-compose.dev.yml` | new `heavy` service, same bind mount, cluster env |
| `docker-stack.yml` | new `qcluster-heavy` service on the heavy image |
| `justfile` | `qcluster-heavy-dev`, `heavy-up`, `heavy-logs` |
| `templates/` | `projects/index.html`, `projects/new.html`, `projects/detail.html`, `runs/detail.html`, `runs/_trail.html`, `cotton/step_tracker.html` |
| `frontend/src/` | no change in v1; htmx does the polling |

`INSTALLED_APPS`, local apps block only:

```python
INSTALLED_APPS = [
    "apps.core",
    "apps.users",
    "apps.projects",
    "apps.runs",
    "apps.creative",
    "apps.voices",
    "apps.renders",
    "apps.api",
    "apps.pages",
    "apps.dashboard",
    "apps.orgs",
    # ... leynor's third-party block unchanged
]
```

`config/urls.py`, the new lines:

```python
path("projects/", include("apps.projects.urls")),
path("runs/", include("apps.runs.urls")),
```

`config/settings/base.py`, the new block:

```python
REEL_ARTIFACT_ROOT = Path(env("REEL_ARTIFACT_ROOT", default=str(BASE_DIR / "var" / "artifacts")))
REEL_LLM_MODEL = env("REEL_LLM_MODEL", default="")
REEL_WHISPER_SIZE = env("REEL_WHISPER_SIZE", default="base.en")
REEL_RENDER_QUALITY = env("REEL_RENDER_QUALITY", default="delivery")
REEL_MIN_FREE_GB = env.int("REEL_MIN_FREE_GB", default=10)

Q_CLUSTER = {
    "name": env("Q_CLUSTER_NAME", default="reel-default"),
    "orm": "default",
    "workers": env.int("Q_CLUSTER_WORKERS", default=2),
    "timeout": env.int("Q_CLUSTER_TIMEOUT", default=1500),
    "retry": env.int("Q_CLUSTER_RETRY", default=1800),   # must exceed timeout
    "max_attempts": 1,
    "catch_up": False,
}
```

Heavy container overrides: `Q_CLUSTER_NAME=reel-heavy`,
`Q_CLUSTER_WORKERS=1`, `Q_CLUSTER_TIMEOUT=3600`, `Q_CLUSTER_RETRY=3900`.

`dev/docker-compose.dev.yml`, new service:

```yaml
  heavy:
    build:
      context: ..
      dockerfile: dev/Dockerfile.heavy
    container_name: reel-heavy
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/db
      - Q_CLUSTER_NAME=reel-heavy
      - Q_CLUSTER_WORKERS=1
      - Q_CLUSTER_TIMEOUT=3600
      - Q_CLUSTER_RETRY=3900
      - OTEL_ENABLED=false
    volumes:
      - ..:/app            # var/artifacts is shared through this mount
      - django_venv:/app/.venv
```

`pyproject.toml`, dependencies:

```toml
[project]
name = "reel-playbook"

dependencies = [
    # ... leynor's base list unchanged ...
    "pydantic>=2.11",
    "pydantic-ai>=2.60,<3",
]

[project.optional-dependencies]
heavy = ["torch>=2.6", "faster-whisper>=1.1", "pocket-tts>=4.0.1"]
```

The `pytorch-cpu` index and `[tool.uv.sources] torch` move to the same file
unchanged. `uv sync` builds the web image; `uv sync --extra heavy` builds the
heavy image.

`var/` is already ignored by leynor's `.gitignore`, so artifacts never enter git.

## Phase 0-2 work breakdown

Work in `.worktrees/django-app` (see the repo's worktree rule). Every phase ends
with a green `just test`.

### Phase 0: spikes, no product code

Three spikes. Each one answers a question that can kill the plan.

**0.1 Heavy image renders a clip.**
Files: `dev/Dockerfile.heavy`, `dev/docker-compose.dev.yml` (heavy service only).
Steps:
- Write the Dockerfile: leynor's base steps, then `apt-get install ffmpeg
  nodejs chromium`, then `uv sync --extra heavy`.
- `docker compose -f dev/docker-compose.dev.yml build heavy`.
- Inside it run: `ffmpeg -version`, `npx hyperframes --version`,
  `python -c "import torch, faster_whisper, pocket_tts"`.
- Render a 3 second clip from a hand-written HTML into `/app/var/artifacts/spike/out.mp4`.
Exit: mp4 exists, `ffprobe` reports 3.0s at 1080x1920.

**0.2 `Store` on local disk.**
Files: `apps/runs/artifacts.py`, `apps/runs/tests/test_artifacts.py`.
Test first:
```python
def test_put_get_sha(tmp_path):
    store = FileStore(tmp_path)
    sha = store.put("run/a.html", "<p>hi</p>")
    assert store.get("run/a.html") == b"<p>hi</p>"
    assert len(sha) == 64

def test_rejects_traversal(tmp_path):
    with pytest.raises(UnsafePath):
        FileStore(tmp_path).put("../escape.txt", "x")
```
Then implement `put` (temp file in the same directory, `os.replace`), `get`,
`tmpdir`, `UnsafePath`, `ArtifactMissing`.
Exit: tests pass; a file put through `Store` is readable by `ffprobe` from the
same path.

**0.3 One pure step moved into an app.**
Files: `apps/projects/spec.py`, `apps/projects/tests/test_spec.py`; smallest
port is `content.py` (75 lines).
Steps: copy it, change imports, run the existing `tests/test_content_compose.py`
cases against the new path, delete the old file in phase 2.
Exit: the moved module imports inside a Django test process and its original
tests pass unchanged.

Phase 0 gate: all three spikes green, no `models.py`, no migrations. If the
heavy image cannot run Chromium under the sandbox, stop and answer the open
question about ffmpeg plus Pillow before phase 1.

### Phase 1: leynor becomes the app

**1.1 Fork in.**
Files: whole leynor tree.
Steps: copy everything except `.git`, `.venv`, `node_modules`, `media`,
`staticfiles`. Keep `src/` and `tests/` of the old engine in place for now.
Rename in `pyproject.toml`, `mise.toml`, `frontend/package.json`, `README.md`,
`.env.example`.
Test: `just test` (leynor's suite) passes on the copied tree.

**1.2 Strip the SaaS surface.**
Files: `apps/pages/views.py`, `apps/pages/urls.py`, `apps/pages/sitemaps.py`
(delete), `templates/pages/privacy.html`, `terms.html` (delete),
`config/urls.py`.
Test: `client.get("/")` returns 302 to `/dashboard/` when logged in, 302 to
`/accounts/login/` otherwise; `client.get("/terms/")` is 404.

**1.3 Rename and settings.**
Files: `config/settings/base.py`, `.env.example`, `docker-stack.yml`.
Steps: add the `REEL_*` block, env-driven `Q_CLUSTER`, the five apps, the two
URL includes. Add the heavy service to `dev/docker-compose.dev.yml` and
`qcluster-heavy` to `docker-stack.yml`.
Test: `DJANGO_SETTINGS_MODULE=config.settings.test python manage.py check`
passes with the five apps listed and no `models.py` yet; app labels appear in
`manage.py showmigrations` with no pending migrations.

**1.4 Dev stack green.**
Steps: `just dev-slim`, signup, personal org, admin login, `just test`.
Exit: `/dashboard/` renders, `/projects/` returns 404 until phase 5 (or an empty
page if the urlconf entry lands now), heavy container stays up and idle.

### Phase 2: engine into the apps, no database

The point of this phase: every step runs as a function in its app, tested with
fakes, before a single model exists.

**2.1 `projects/spec.py` and `projects/steps.py`.**
Files: move `content.py`, `steps.py`; update `Step` to be a `TextChoices` and
keep `StepSpec` for names, inputs, outputs, skills, prompts.
Test: `test_steps_order` asserts `[step.value for step in Step]` equals the
route order; `test_spec_rejects_bad_scene_count` ports an existing case.

**2.2 `projects/gates.py`.**
Files: `apps/projects/gates.py`, `apps/projects/tests/test_gates.py`.
Content: `HUMAN_GATES = {Step.BOARD, Step.PRINT}`, `AUTO_GATES`,
`next_step(after: Step) -> Step | None`, `needs_human(step) -> bool`.
Test: `test_board_and_print_need_human`, `test_last_step_has_no_successor`.

**2.3 `creative/`.**
Files: move `creative.py` to `validators.py`, `agents.py`, `graphs.py`,
`skills.py`; new `services.py: draft(step, brief) -> DraftResult`.
Test: the existing `test_creative.py` cases move as is; `test_graph_runs_without_model`
uses fake deps; `test_model_comes_from_settings` asserts
`build_agents` receives `settings.REEL_LLM_MODEL`.
No torch, no network: the agents are never constructed in tests.

**2.4 `voices/`.**
Files: move `voice.py`, `tts.py`, `align.py`, `voice_audit.py`; new `cues.py`
(`CueData`), new `services.py: run_voice(spec, store) -> VoiceResult`.
Steps: wrap `torch`, `faster_whisper`, `pocket_tts` imports inside function
bodies. Inject the TTS callable so tests pass a writer of silent wavs.
Test: `test_run_voice_writes_master_and_cues` with a fake TTS and a `tmp_path`
store; `test_cue_times_are_monotonic`.

**2.5 `renders/`.**
Files: move `design.py`, `imagetools.py` to `media.py`, `compose.py`,
`timeline.py`; new `video.py` with `encode(compose_dir, out_path, quality)` and
`check(video)`, both `subprocess`. New `services.py` with `run_look`,
`run_compose`, `run_print`.
Test: golden HTML for the fixture spec, byte-identical to the pre-move output;
timeline report snapshot; `test_video_calls_ffmpeg` monkeypatches `subprocess.run`
and asserts the argument list, so no ffmpeg is needed in CI.

**2.6 `runs/artifacts.py` finished.**
Files: delete `src/reel_playbook/storage.py`; keep the `Store` from 0.2; add
`artifact_path(instance, filename)` that builds
`<org_uuid>/<project_uuid>/<run_uuid>/<path>`.
Test: `test_artifact_path_is_run_scoped`, `test_parts_reject_dotdot`.

**2.7 `runs/registry.py`.**
Files: `apps/runs/registry.py`.
Content: `RUNNERS: dict[Step, Callable[[RunInput], StepResult]]` mapping each
step to the function in `creative`, `voices`, or `renders`; `runner(step)`
resolves inside the function body, imports the module lazily.
Test: `test_every_step_has_a_runner` and `test_registry_import_loads_no_heavy_module`
(assert `"torch" not in sys.modules` after importing the registry).

**2.8 Delete the old code.**
Files: delete `src/reel_playbook/` entirely, including `db/`, `cli.py`,
`build.py`, `book.py`; delete `[project.scripts]`; move `tests/` snapshots per
app.
Test: `just test` green; `tests/test_web_boot.py` and `tests/test_layering.py`
green.
Exit for phase 2: the whole pipeline runs from app functions with fakes, no
models, no migrations, no torch in the web process. Phase 3 then adds the schema
these functions will be called with.

## Testing

| Suite | What it proves |
|---|---|
| `tests/test_web_boot.py` | importing the URLconf loads no torch and no whisper |
| `tests/test_layering.py` | app import graph matches the context map; no cycles |
| `projects/tests/` | gate order, human gates, immutable spec, `next_step`, one-active-run index |
| `runs/tests/` | resume after kill, no duplicate artifacts, cancel, sweeper, `run_state` shape |
| `creative/tests/` | validators, draft graph with fake deps, golden prompts |
| `voices/tests/` | cue ordering, timing bounds, mix report |
| `renders/tests/` | golden cues to HTML, timeline report, frame snapshots |
| view tests | cross-org denied, download auth, partial equals payload, forms without JS |

The golden comparison is the contract: same spec in, same cues, same HTML, same
timeline report out, before and after the move. Take the snapshots from the
current code first.

## Build phases

| Phase | Scope | Exit criteria |
|---|---|---|
| 0 | Spikes: `Store` with a fake root; one step function moved into an app; 3 second clip from the heavy image | One step runs end to end from a Django app |
| 1 | leynor into the repo, rename, strip marketing and SaaS pages, `/` to `/dashboard/` | `just dev`, signup, org, admin green |
| 2 | Move engine into the five apps, delete `db/`, `storage.py`, `cli.py`; port `book.py` and `build.py` into services | Golden tests pass; layering and web-boot tests pass |
| 3 | Models, migrations, tenancy, admin | Migrations clean; cross-org denied; auditlog on roots |
| 4 | `RunProject`, `execute` task, two clusters, resume, cancel, sweeper | Kill worker mid-run; resume with no duplicate artifacts; sweeper re-enqueues |
| 5 | UI: list, new, detail, tracker partial, approve, cancel, artifact views | Create project, run, approve, download, all without JS |
| 6 | Production artifact delivery and backups | Unauthorized download denied; restore drill passes |
| 7 | Load and disk test | 10 concurrent projects, one heavy job at a time, no OOM; disk-full refuses cleanly; compose-cache decision made |
| 8 | Cloud switch, later | S3 backend, signed redirects, no model changes |

## First ten tasks

1. Fork leynor into the repo root, rename, delete marketing and SaaS pages,
   redirect `/` to `/dashboard/`.
2. Create the five apps with `models.py`, `apps.py`, `admin.py`, `tests/`.
3. Move `steps.py` and `content.py` into `projects`; add `gates.py` and the
   transition methods.
4. Move `creative.py`, `agents.py`, `graphs.py`, `skills.py` into `creative`.
5. Move `voice.py`, `tts.py`, `align.py`, `voice_audit.py` into `voices`; lazy
   imports only; add `CueData`.
6. Move `design.py`, `imagetools.py`, `compose.py`, `timeline.py` into
   `renders`; add `video.py` for subprocess calls.
7. Delete `db/`, `cli.py`, `storage.py`; write `runs/artifacts.py` with the
   `Store` contract and path guards.
8. Write migrations: `Project`, `Spec`, `Gate`, `Log`, `Run`, `StepRun`,
   `Artifact`, `Idea`, `Hook`, `Beat`, `Cue`, plus the active-run index.
9. Implement `registry.py`, `RunProject.execute`, `tasks.execute`, heartbeat,
   sweeper.
10. Add `run_state`, the Cotton tracker, the htmx partial, artifact download,
    approve and cancel forms.

## Not doing

- No separate domain package, no ports and adapters layer, no repository over
  the ORM.
- No CLI, no `reel` console script, no product-facing management commands. The
  legacy JSON import is a throwaway command, deleted after the first import.
- No DMR endpoints for runs or gates.
- No Svelte islands for v1.
- No `llm` cluster for v1. Drafting runs inside the run task.
- No billing, subscriptions, plans, quotas, entitlements, Stripe, usage
  metering.
- No API tokens, no public API.
- No outbox, no SSE, no Celery, no Redis, no Kubernetes, no schema-per-tenant.
- No blob dedupe, no compose cache in v1, no video in Postgres.

## Risks

- The real work is splitting `book.py` (577 lines) and `build.py` (634 lines)
  while keeping the golden snapshots byte-identical.
- Moving media code into apps invites module-level torch imports under Django
  startup. The web-boot test is the only thing that catches it; write it first.
- App boundaries can rot into cycles once `runs` imports `voices` and `renders`
  and both import `projects`. The layering test is the guard.
- One heavy worker limits throughput. Acceptable in private use; split with
  measurements.
- The heavy image is large and slow to build. Pin versions, cache layers, keep
  torch on the CPU index.
- q2 with Postgres as broker: `retry` must exceed `timeout`, and the advisory
  lock must be released on every exit path, or a dead worker blocks a project.
- Chromium and ffmpeg must not see the host filesystem or the network, even on a
  private host.
- A JSON textarea for the spec is a real UX cost. If it hurts in phase 5, spend
  the day on per-field forms.
- leynor assumptions: `async_task(..., cluster=...)` and per-container cluster
  settings are unverified until phase 4 runs.

## Open questions

- Keep all runs forever, or prune artifacts after N days?
- Single user only, or invite collaborators into the one org?
- HyperFrames in the container, or compose to ffmpeg and Pillow to drop
  Chromium?
- Is a cheap preview render worth a separate step before the final render?
- Bring the compose cache back as `CacheKey`, or key compose output by spec hash
  in the artifact path?
