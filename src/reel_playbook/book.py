"""The playbook as a class: one project, one state machine, one ledger.

    book = ReelPlaybook.create(Workspace(), "04-five-minutes")
    book.status()
    book.pass_gate("board", "spec + 5 scenes; est durations")
    book.rewind("voice", "one word changed")

Six steps, six gates, no forward move without a recorded gate. The artifact
proves nothing on its own; the gate record is what counts. The database row is
the project; ``manifest.json`` is the portable export.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agents import Agents, build_agents
from .graphs import run_draft
from .models import (
    Cue,
    DraftResult,
    FlowTracker,
    GateRecord,
    LogEntry,
    StatusReport,
    StepStatus,
    TimelineReport,
    Tokens,
    VERSION,
    utcnow,
)
from .steps import BY_ID, BY_STATE, STATES, STEPS, StepSpec, resolve
from .storage import Catalog, Store, Workspace
from .timeline import check_timeline

SPEC_TOKENS = ("fps", "width", "height", "tolerance_frames", "language")
INT = re.compile(r"^-?\d+$")
FLOAT = re.compile(r"^-?\d+\.\d+$")


class StateError(RuntimeError):
    """An illegal move: wrong step, locked token, no attempts left."""


class ReelPlaybook:
    def __init__(
        self,
        workspace: Workspace,
        slug: str,
        record: dict,
        *,
        llm_model: str | None = None,
    ):
        self.workspace = workspace
        self.slug = slug
        self.root = workspace.project_dir(slug)
        self._record = dict(record)
        self.tokens = Tokens(**json.loads(record["tokens_json"]))
        self.locked_at: dict[str, str] = json.loads(record["locked_json"] or "{}")
        self.max_attempts = int(record["max_attempts"])
        self.llm_model = llm_model
        self._catalog = workspace.catalog()
        self._gates = {
            step: GateRecord(
                step=step,
                result=gate.get("result"),
                attempts=int(gate.get("attempts") or 0),
                evidence=gate.get("evidence"),
                at=_time(gate.get("at")),
            )
            for step, gate in self._catalog.get_gates(slug).items()
        }
        self._agents: Agents | None = None

    # -- construction ---------------------------------------------------

    @classmethod
    def create(
        cls,
        workspace: Workspace | Path | str | None,
        slug: str,
        *,
        fps: int = 30,
        size: tuple[int, int] = (1080, 1920),
        language: str = "english",
        tts_model: str = "english",
        max_attempts: int = 3,
        llm_model: str | None = None,
    ) -> "ReelPlaybook":
        ws = _workspace(workspace)
        if fps <= 0:
            raise StateError("fps must be positive")
        if max_attempts <= 0:
            raise StateError("max_attempts must be positive")
        root = ws.project_dir(slug)
        catalog = ws.catalog()
        if catalog.get_project(slug) is not None:
            raise StateError(f"{slug} already exists; open it or pick another slug")
        if root.exists() and any(root.iterdir()):
            raise StateError(f"{root} is not empty; pick another slug")
        for name in ("assets", "assets/visuals", "compositions", "boards"):
            (root / name).mkdir(parents=True, exist_ok=True)
        width, height = size
        stamp = utcnow().isoformat(timespec="seconds")
        record = {
            "slug": slug,
            "state": "IDEA",
            "version": VERSION,
            "root": str(root),
            "fps": fps,
            "width": width,
            "height": height,
            "duration_s": None,
            "max_attempts": max_attempts,
            "tokens_json": json.dumps(
                Tokens(
                    fps=fps,
                    width=width,
                    height=height,
                    language=language,
                    tts_model=tts_model,
                ).public()
            ),
            "locked_json": json.dumps({key: "IDEA" for key in SPEC_TOKENS}),
            "created_at": stamp,
            "updated_at": stamp,
        }
        book = cls(ws, slug, record, llm_model=llm_model)
        book._log("init", "IDEA", "IDEA", f"{width}x{height} @{fps}fps, tts {tts_model}")
        book.save()
        return book

    @classmethod
    def open(
        cls,
        workspace: Workspace | Path | str | None,
        slug: str,
        *,
        llm_model: str | None = None,
    ) -> "ReelPlaybook":
        ws = _workspace(workspace)
        record = ws.catalog().get_project(slug)
        if record is None:
            raise StateError(f"{slug} not found in {ws.root}; run `reel init {slug}`")
        return cls(ws, slug, record, llm_model=llm_model)

    @classmethod
    def open_or_create(cls, workspace, slug: str, **kwargs) -> "ReelPlaybook":
        ws = _workspace(workspace)
        if ws.catalog().get_project(slug) is not None:
            return cls.open(ws, slug, llm_model=kwargs.get("llm_model"))
        return cls.create(ws, slug, **kwargs)

    # -- lookups --------------------------------------------------------

    @property
    def path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def state(self) -> str:
        return self._record["state"]

    @state.setter
    def state(self, value: str) -> None:
        self._record["state"] = value

    @property
    def gates(self) -> dict[str, GateRecord]:
        return dict(self._gates)

    def spec(self, step: str | StepSpec) -> StepSpec:
        if isinstance(step, StepSpec):
            return step
        try:
            return resolve(step)
        except KeyError as exc:
            raise StateError(str(exc)) from exc

    @property
    def current(self) -> StepSpec | None:
        return BY_STATE.get(self.state)

    # -- transitions ----------------------------------------------------

    def pass_gate(self, step: str, evidence: str) -> str:
        spec = self.spec(step)
        if self.state != spec.state:
            open_step = self.current
            raise StateError(
                f"open step is {open_step.id if open_step else 'DONE'}, not {spec.id}"
            )
        evidence = evidence.strip()
        if not evidence:
            raise StateError("a gate needs evidence: a number, a quote, a checklist row")
        gate = self._gates.get(spec.id) or GateRecord(step=spec.id)
        if gate.attempts >= self.max_attempts:
            raise StateError(
                f"{spec.id}: {self.max_attempts} attempts used; stop and report"
            )
        for key in spec.locks:
            if self.tokens.get(key) is None:
                raise StateError(f"set {key} before passing {spec.id}")
            self.locked_at[key] = spec.next_state
        gate.result = "pass"
        gate.evidence = evidence
        gate.reason = None
        gate.at = utcnow()
        self._gates[spec.id] = gate
        previous = self.state
        self.state = spec.next_state
        self._log("pass", previous, self.state, f"{spec.id}: {evidence}")
        self.save()
        return self.state

    def fail_gate(self, step: str, reason: str) -> str:
        spec = self.spec(step)
        if self.state != spec.state:
            raise StateError(f"open step is {self.state}, not {spec.state}")
        reason = reason.strip()
        if not reason:
            raise StateError("a failure needs a reason")
        gate = self._gates.get(spec.id) or GateRecord(step=spec.id)
        gate.attempts += 1
        gate.result = "fail"
        gate.reason = reason
        gate.at = utcnow()
        self._gates[spec.id] = gate
        self._log("fail", self.state, self.state, f"{spec.id}: {reason}")
        self.save()
        if gate.attempts >= self.max_attempts:
            raise StateError(
                f"{spec.id} failed {gate.attempts} times; stop and report"
            )
        return self.state

    def rewind(self, step: str, reason: str) -> str:
        spec = self.spec(step)
        if spec.index > self._step_index():
            raise StateError(f"cannot rewind forward: {self.state} -> {spec.state}")
        for step_id in [key for key in self._gates if BY_ID[key].index >= spec.index]:
            del self._gates[step_id]
        self._catalog.delete_gates_from(
            self.slug,
            [key for key in BY_ID if BY_ID[key].index >= spec.index],
        )
        for token, locked_state in list(self.locked_at.items()):
            if STATES.index(locked_state) >= STATES.index(spec.state):
                del self.locked_at[token]
        if spec.index <= BY_ID["voice"].index:
            self._catalog.put_cues(self.slug, [])
            captions = self.root / "captions.json"
            if captions.exists():
                captions.unlink()
        previous = self.state
        self.state = spec.state
        self._log("rewind", previous, self.state, f"{spec.id}: {reason}")
        self.save()
        return self.state

    def set_token(self, key: str, value: Any) -> Any:
        if key in SPEC_TOKENS:
            raise StateError(f"{key} is the delivery spec; start a new project")
        lock = self.locked_at.get(key)
        if lock:
            raise StateError(
                f"{key} locked at {lock}; run `reel rewind {self.slug} "
                f"{BY_STATE[lock].id}`"
            )
        parsed = self._parse(value)
        self.tokens.set(key, parsed)
        self._log("set", self.state, self.state, f"{key}={parsed}")
        self.save()
        return parsed

    # -- views ----------------------------------------------------------

    def flow(self) -> FlowTracker:
        steps: list[StepStatus] = []
        for spec in STEPS:
            gate = self._gates.get(spec.id)
            if gate and gate.result == "pass":
                kind = "done"
            elif self.state == spec.state:
                kind = "failed" if gate and gate.result == "fail" else "current"
            else:
                kind = "locked"
            steps.append(
                StepStatus(
                    id=spec.id,
                    index=spec.index,
                    name=spec.name,
                    description=spec.description,
                    status=kind,
                    attempts=gate.attempts if gate else 0,
                    artifacts={p: self._has(p) for p in spec.artifacts},
                    evidence=(gate.evidence if gate and gate.result == "pass" else None),
                )
            )
        done = sum(1 for step in steps if step.status == "done")
        current = next(
            (step for step in steps if step.status in ("current", "failed")), None
        )
        return FlowTracker(
            state=self.state,
            steps=steps,
            current=current,
            progress=round(done / len(STEPS), 3),
            done=self.state == "DONE",
        )

    def status(self, *, logs: int = 5) -> StatusReport:
        entries = [
            LogEntry(
                at=_time(row["at"]) or utcnow(),
                action=row["action"],
                from_state=row["from_state"],
                to_state=row["to_state"],
                note=row["note"],
            )
            for row in self._catalog.get_logs(self.slug, limit=logs)
        ]
        return StatusReport(
            project=self.slug,
            version=str(self._record["version"]),
            state=self.state,
            flow=self.flow(),
            tokens=self.tokens.public(),
            locked=dict(self.locked_at),
            logs=entries,
        )

    def cues(self) -> list[Cue]:
        return [
            Cue(
                scene=int(row["scene"]),
                start=float(row["start_s"]),
                end=float(row["end_s"]),
                text=row["text"],
            )
            for row in self._catalog.get_cues(self.slug)
        ]

    def cue_dicts(self) -> list[dict]:
        return [cue.model_dump() for cue in self.cues()]

    def assets(self) -> list[dict]:
        return self._catalog.get_assets(self.slug)

    def timeline(self, video: Path | str | None = None) -> TimelineReport:
        report = check_timeline(
            self.root,
            self.cue_dicts(),
            fps=float(self.tokens.fps),
            tolerance_frames=int(self.tokens.tolerance_frames),
            duration=self.tokens.duration,
            video=Path(video) if video is not None else None,
        )
        self._log(
            "timeline",
            self.state,
            self.state,
            "ok" if report.ok else f"{len(report.errors)} error(s)",
        )
        self.save()
        return report

    # -- drafting -------------------------------------------------------

    def draft(self, step: str, brief: str = "") -> DraftResult:
        spec = self.spec(step)
        if not spec.llm:
            raise StateError(f"{spec.id} is not a drafting step")
        if self._agents is None:
            self._agents = build_agents(self.llm_model)
        result = run_draft(spec.id, brief or (spec.prompt or ""), self._agents.deps())
        self._log("draft", self.state, self.state, f"{spec.id}: {len(result.revised)} chars")
        self.save()
        return result

    # -- persistence ----------------------------------------------------

    def save(self) -> None:
        self._record.update(
            state=self.state,
            version=VERSION,
            root=str(self.root),
            fps=self.tokens.fps,
            width=self.tokens.width,
            height=self.tokens.height,
            duration_s=self.tokens.duration,
            max_attempts=self.max_attempts,
            tokens_json=json.dumps(self.tokens.public()),
            locked_json=json.dumps(self.locked_at),
            updated_at=utcnow().isoformat(timespec="seconds"),
        )
        self._catalog.put_project(self._record)
        for gate in self._gates.values():
            self._catalog.put_gate(
                self.slug,
                {
                    "step": gate.step,
                    "result": gate.result,
                    "attempts": gate.attempts,
                    "evidence": gate.evidence,
                    "at": gate.at.isoformat() if gate.at else None,
                },
            )
        self._write_manifest()

    def _write_manifest(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "slug": self.slug,
            "version": self._record["version"],
            "state": self.state,
            "updated_at": self._record["updated_at"],
            "tokens": self.tokens.public(),
            "locked_at": self.locked_at,
            "gates": {
                step: gate.model_dump(mode="json")
                for step, gate in sorted(self._gates.items())
            },
            "cues": self.cue_dicts(),
            "assets": [
                {
                    "ref": f"{row['sha256']}.{row['ext']}",
                    "role": row["role"],
                    "kind": row["kind"],
                    "bytes": row["bytes"],
                    "meta": json.loads(row["meta_json"] or "{}"),
                }
                for row in self.assets()
            ],
            "source": str(self.workspace.db_path),
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n")

    # -- internals ------------------------------------------------------

    @property
    def store(self) -> Store:
        return self.workspace.store()

    @property
    def catalog(self) -> Catalog:
        return self._catalog

    def _step_index(self) -> int:
        spec = self.current
        return spec.index if spec else len(STEPS) + 1

    def _has(self, pattern: str) -> bool:
        if any(ch in pattern for ch in "*?[]"):
            return any(self.root.glob(pattern))
        return (self.root / pattern).exists()

    def _log(self, action: str, from_state: str, to_state: str, note: str | None) -> None:
        self._catalog.add_log(
            self.slug,
            {
                "at": utcnow().isoformat(timespec="seconds"),
                "action": action,
                "from_state": from_state,
                "to_state": to_state,
                "note": note,
            },
        )

    @staticmethod
    def _parse(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if INT.match(value):
            return int(value)
        if FLOAT.match(value):
            return float(value)
        return value

    def __repr__(self) -> str:
        return f"ReelPlaybook({self.slug}, state={self.state})"


def _workspace(value: Workspace | Path | str | None) -> Workspace:
    return value if isinstance(value, Workspace) else Workspace(value)


def _time(value) -> Any:
    if not value or not isinstance(value, str):
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
