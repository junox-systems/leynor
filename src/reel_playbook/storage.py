"""One workspace, one database, content-addressed blobs.

Portable by design: TEXT ids, ISO timestamps, no SQLite-only syntax beyond
``INSERT ... ON CONFLICT`` (Postgres 9.5+ has the same). Swapping to Postgres for
the Django app means a connection and a paramstyle, not a schema rewrite.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  slug TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  version TEXT NOT NULL,
  root TEXT NOT NULL,
  fps INTEGER NOT NULL,
  width INTEGER NOT NULL,
  height INTEGER NOT NULL,
  duration_s DOUBLE PRECISION,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  tokens_json TEXT NOT NULL,
  locked_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
  sha256 TEXT PRIMARY KEY,
  ext TEXT NOT NULL,
  kind TEXT NOT NULL,
  media_type TEXT,
  bytes BIGINT NOT NULL,
  duration_s DOUBLE PRECISION,
  width INTEGER,
  height INTEGER,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_assets (
  slug TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  role TEXT NOT NULL,
  meta_json TEXT,
  PRIMARY KEY (slug, sha256, role)
);
CREATE TABLE IF NOT EXISTS cache_keys (
  key TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL,
  tool TEXT NOT NULL,
  tool_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gates (
  slug TEXT NOT NULL,
  step TEXT NOT NULL,
  result TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  evidence TEXT,
  at TEXT,
  PRIMARY KEY (slug, step)
);
CREATE TABLE IF NOT EXISTS logs (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL,
  at TEXT NOT NULL,
  action TEXT NOT NULL,
  from_state TEXT NOT NULL,
  to_state TEXT NOT NULL,
  note TEXT
);
CREATE INDEX IF NOT EXISTS logs_slug_at ON logs (slug, at);
CREATE TABLE IF NOT EXISTS cues (
  slug TEXT NOT NULL,
  idx INTEGER NOT NULL,
  scene INTEGER NOT NULL,
  start_s DOUBLE PRECISION NOT NULL,
  end_s DOUBLE PRECISION NOT NULL,
  text TEXT NOT NULL,
  PRIMARY KEY (slug, idx)
);
CREATE TABLE IF NOT EXISTS renders (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  duration_s DOUBLE PRECISION,
  fps DOUBLE PRECISION,
  loudness DOUBLE PRECISION,
  peak DOUBLE PRECISION,
  verified_at TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


class Workspace:
    """Root of all data. Nothing outside it is written."""

    def __init__(self, root: Path | str | None = None):
        self.root = Path(
            root or os.environ.get("REEL_HOME") or Path.home() / "Videos" / "reels"
        ).resolve()
        self.db_path = self.root / "reel.sqlite"
        self.blobs = self.root / "blobs"
        self.projects = self.root / "projects"
        self.specs = self.root / "specs"
        self.tmp = self.root / "tmp"
        for path in (self.root, self.blobs, self.projects, self.specs, self.tmp):
            path.mkdir(parents=True, exist_ok=True)

    def project_dir(self, slug: str) -> Path:
        if not SLUG.match(slug):
            raise ValueError(f"bad slug {slug!r}; lowercase letters, digits, dashes")
        return self.projects / slug

    @contextmanager
    def scratch(self):
        path = self.tmp / new_id()
        path.mkdir(parents=True)
        try:
            yield path
        finally:
            shutil.rmtree(path, ignore_errors=True)

    def assert_inside(self, path: Path) -> Path:
        resolved = path.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError(f"{resolved} is outside the workspace {self.root}")
        return resolved

    def store(self) -> "Store":
        return Store(self)

    def catalog(self) -> "Catalog":
        return Catalog(self.db_path)


class Store:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def _blob(self, sha: str, ext: str) -> Path:
        return self.workspace.blobs / sha[:2] / sha[2:4] / f"{sha}.{ext}"

    def path(self, ref: str) -> Path:
        sha, _, ext = ref.partition(".")
        return self._blob(sha, ext)

    def put_bytes(self, data: bytes, ext: str) -> tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        ref = f"{sha}.{ext}"
        target = self._blob(sha, ext)
        if target.exists():
            return sha, ref
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.workspace.tmp / f"{uuid.uuid4().hex}.{ext}"
        tmp.write_bytes(data)
        os.replace(tmp, target)
        return sha, ref

    def put_file(self, path: Path, ext: str | None = None) -> tuple[str, str]:
        return self.put_bytes(path.read_bytes(), ext or path.suffix.lstrip(".") or "bin")

    def materialize(self, ref: str, dest: Path) -> Path:
        source = self.path(ref)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        shutil.copyfile(source, tmp)
        os.replace(tmp, dest)
        return dest

    def key(self, *parts: object) -> str:
        raw = json.dumps(parts, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()


class Catalog:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # projects ---------------------------------------------------------

    def put_project(self, record: dict) -> None:
        columns = (
            "slug, state, version, root, fps, width, height, duration_s, "
            "max_attempts, tokens_json, locked_json, created_at, updated_at"
        )
        values = tuple(record[k] for k in (
            "slug", "state", "version", "root", "fps", "width", "height",
            "duration_s", "max_attempts", "tokens_json", "locked_json",
            "created_at", "updated_at",
        ))
        self.conn.execute(
            f"INSERT INTO projects ({columns}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(slug) DO UPDATE SET state=excluded.state, "
            "version=excluded.version, root=excluded.root, fps=excluded.fps, "
            "width=excluded.width, height=excluded.height, "
            "duration_s=excluded.duration_s, max_attempts=excluded.max_attempts, "
            "tokens_json=excluded.tokens_json, "
            "locked_json=excluded.locked_json, updated_at=excluded.updated_at",
            values,
        )
        self.conn.commit()

    def get_project(self, slug: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM projects WHERE slug=?", (slug,)).fetchone()
        return dict(row) if row else None

    def list_projects(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM projects ORDER BY slug").fetchall()
        return [dict(r) for r in rows]

    # gates and logs ---------------------------------------------------

    def put_gate(self, slug: str, gate: dict) -> None:
        self.conn.execute(
            "INSERT INTO gates (slug, step, result, attempts, evidence, at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(slug, step) DO UPDATE SET "
            "result=excluded.result, attempts=excluded.attempts, "
            "evidence=excluded.evidence, at=excluded.at",
            (slug, gate["step"], gate.get("result"), gate.get("attempts", 0),
             gate.get("evidence"), gate.get("at")),
        )
        self.conn.commit()

    def get_gates(self, slug: str) -> dict[str, dict]:
        rows = self.conn.execute("SELECT * FROM gates WHERE slug=?", (slug,)).fetchall()
        return {r["step"]: dict(r) for r in rows}

    def delete_gates_from(self, slug: str, steps: list[str]) -> None:
        for step in steps:
            self.conn.execute("DELETE FROM gates WHERE slug=? AND step=?", (slug, step))
        self.conn.commit()

    def add_log(self, slug: str, entry: dict) -> None:
        self.conn.execute(
            "INSERT INTO logs (id, slug, at, action, from_state, to_state, note) "
            "VALUES (?,?,?,?,?,?,?)",
            (new_id(), slug, entry["at"], entry["action"], entry["from_state"],
             entry["to_state"], entry.get("note")),
        )
        self.conn.commit()

    def get_logs(self, slug: str, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM logs WHERE slug=? ORDER BY at DESC LIMIT ?", (slug, limit)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # assets -----------------------------------------------------------

    def put_asset(self, record: dict) -> None:
        self.conn.execute(
            "INSERT INTO assets (sha256, ext, kind, media_type, bytes, duration_s, "
            "width, height, created_at) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(sha256) DO NOTHING",
            (record["sha256"], record["ext"], record["kind"],
             record.get("media_type"), record["bytes"], record.get("duration_s"),
             record.get("width"), record.get("height"), record["created_at"]),
        )
        self.conn.commit()

    def link_asset(self, slug: str, sha: str, role: str, meta: dict | None = None) -> None:
        self.conn.execute(
            "INSERT INTO project_assets (slug, sha256, role, meta_json) VALUES (?,?,?,?) "
            "ON CONFLICT(slug, sha256, role) DO UPDATE SET meta_json=excluded.meta_json",
            (slug, sha, role, json.dumps(meta or {})),
        )
        self.conn.commit()

    def get_assets(self, slug: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT a.*, pa.role, pa.meta_json FROM project_assets pa "
            "JOIN assets a ON a.sha256 = pa.sha256 WHERE pa.slug=? ORDER BY pa.role",
            (slug,),
        ).fetchall()
        return [dict(r) for r in rows]

    def cache_get(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT sha256 FROM cache_keys WHERE key=?", (key,)
        ).fetchone()
        return row["sha256"] if row else None

    def cache_put(self, key: str, sha: str, tool: str, version: str) -> None:
        self.conn.execute(
            "INSERT INTO cache_keys (key, sha256, tool, tool_version, created_at) "
            "VALUES (?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET sha256=excluded.sha256",
            (key, sha, tool, version, now()),
        )
        self.conn.commit()

    # cues and renders -------------------------------------------------

    def put_cues(self, slug: str, cues: list[dict]) -> None:
        self.conn.execute("DELETE FROM cues WHERE slug=?", (slug,))
        self.conn.executemany(
            "INSERT INTO cues (slug, idx, scene, start_s, end_s, text) "
            "VALUES (?,?,?,?,?,?)",
            [(slug, i, c["scene"], c["start"], c["end"], c["text"])
             for i, c in enumerate(cues)],
        )
        self.conn.commit()

    def get_cues(self, slug: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM cues WHERE slug=? ORDER BY idx", (slug,)
        ).fetchall()
        return [dict(r) for r in rows]

    def put_render(self, slug: str, render: dict) -> None:
        self.conn.execute(
            "INSERT INTO renders (id, slug, sha256, duration_s, fps, loudness, peak, "
            "verified_at) VALUES (?,?,?,?,?,?,?,?)",
            (new_id(), slug, render["sha256"], render.get("duration_s"),
             render.get("fps"), render.get("loudness"), render.get("peak"),
             render.get("verified_at")),
        )
        self.conn.commit()

    def get_render(self, slug: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM renders WHERE slug=? ORDER BY verified_at DESC LIMIT 1",
            (slug,),
        ).fetchone()
        return dict(row) if row else None
