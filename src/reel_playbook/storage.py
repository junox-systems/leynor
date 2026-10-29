"""One workspace, one database. Everything but the render lives in the DB.

Artifacts (spec, storyboard, frame, HTML, captions, visuals, master wav) are
rows; binary payloads live once in ``blobs`` and are referenced by sha256. The
only file the pipeline keeps is ``out.mp4``.

The ORM is Django's: same models the future web app will import. ``REEL_DB``
selects the database (default ParadeDB/Postgres 18 on 127.0.0.1:5432).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_id() -> str:
    return uuid.uuid4().hex


class Workspace:
    """Root of all data on disk. Only ``out.mp4`` and scratch live here."""

    def __init__(self, root: Path | str | None = None, db: str | None = None):
        self.root = Path(
            root or os.environ.get("REEL_HOME") or Path.home() / "Videos" / "reels"
        ).resolve()
        self.db_url = db or os.environ.get("REEL_DB") or "postgresql://postgres:postgres@127.0.0.1:5432/reel"
        self.projects = self.root / "projects"
        self.tmp = self.root / "tmp"
        for path in (self.root, self.projects, self.tmp):
            path.mkdir(parents=True, exist_ok=True)

    def project_dir(self, slug: str) -> Path:
        if not SLUG.match(slug):
            raise ValueError(f"bad slug {slug!r}; lowercase letters, digits, dashes")
        path = self.projects / slug
        path.mkdir(parents=True, exist_ok=True)
        return path

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
        return Catalog(self.db_url)


class Store:
    """Content addresses. The bytes live in the database, not on disk."""

    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def sha(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def key(self, *parts: object) -> str:
        raw = json.dumps(parts, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()


class Catalog:
    """Repository over the Django models. One database per process."""

    def __init__(self, url: str):
        from .db import migrate, setup

        setup(url)
        migrate()
        from .db import models

        self.m = models

    # projects ---------------------------------------------------------

    def put_project(self, record: dict) -> None:
        self.m.Project.objects.update_or_create(
            slug=record["slug"],
            defaults={key: record[key] for key in record if key != "slug"},
        )

    def get_project(self, slug: str) -> dict | None:
        return self.m.Project.objects.filter(slug=slug).values().first()

    def list_projects(self) -> list[dict]:
        return list(self.m.Project.objects.order_by("slug").values())

    # gates and logs ---------------------------------------------------

    def put_gate(self, slug: str, gate: dict) -> None:
        self.m.Gate.objects.update_or_create(
            slug=slug,
            step=gate["step"],
            defaults={
                "result": gate.get("result"),
                "attempts": gate.get("attempts", 0),
                "evidence": gate.get("evidence"),
                "at": gate.get("at"),
            },
        )

    def get_gates(self, slug: str) -> dict[str, dict]:
        return {
            row["step"]: row
            for row in self.m.Gate.objects.filter(slug=slug).values()
        }

    def delete_gates_from(self, slug: str, steps: list[str]) -> None:
        self.m.Gate.objects.filter(slug=slug, step__in=steps).delete()

    def add_log(self, slug: str, entry: dict) -> None:
        self.m.Log.objects.create(
            id=new_id(),
            slug=slug,
            at=entry["at"],
            action=entry["action"],
            from_state=entry["from_state"],
            to_state=entry["to_state"],
            note=entry.get("note"),
        )

    def get_logs(self, slug: str, limit: int = 20) -> list[dict]:
        rows = list(
            self.m.Log.objects.filter(slug=slug).order_by("-at").values()[:limit]
        )
        return list(reversed(rows))

    # blobs ------------------------------------------------------------

    def put_blob(
        self, data: bytes, ext: str, kind: str, media_type: str | None = None
    ) -> str:
        sha = hashlib.sha256(data).hexdigest()
        if not self.m.Blob.objects.filter(sha256=sha).exists():
            self.m.Blob.objects.create(
                sha256=sha,
                ext=ext,
                kind=kind,
                media_type=media_type,
                bytes=len(data),
                data=data,
                created_at=now(),
            )
        return sha

    def get_blob(self, sha: str) -> dict | None:
        row = self.m.Blob.objects.filter(sha256=sha).values().first()
        if row and isinstance(row["data"], memoryview):
            row["data"] = bytes(row["data"])
        return row

    # artifacts --------------------------------------------------------

    def put_artifact(
        self,
        slug: str,
        path: str,
        *,
        text: str | None = None,
        sha256: str | None = None,
        kind: str = "file",
        meta: dict | None = None,
    ) -> None:
        if (text is None) == (sha256 is None):
            raise ValueError("an artifact is either text or a blob reference")
        self.m.Artifact.objects.update_or_create(
            slug=slug,
            path=path,
            defaults={
                "kind": kind,
                "text": text,
                "sha256": sha256,
                "meta_json": json.dumps(meta or {}),
            },
        )

    def get_artifact(self, slug: str, path: str) -> dict | None:
        return (
            self.m.Artifact.objects.filter(slug=slug, path=path).values().first()
        )

    def list_artifacts(self, slug: str) -> list[dict]:
        return list(
            self.m.Artifact.objects.filter(slug=slug).order_by("path").values()
        )

    def delete_artifact(self, slug: str, path: str) -> None:
        self.m.Artifact.objects.filter(slug=slug, path=path).delete()

    def artifact_bytes(self, slug: str, path: str) -> bytes | None:
        row = self.get_artifact(slug, path)
        if row is None:
            return None
        if row["text"] is not None:
            return row["text"].encode()
        blob = self.get_blob(row["sha256"])
        return blob["data"] if blob else None

    # cache ------------------------------------------------------------

    def cache_get(self, key: str) -> str | None:
        row = self.m.CacheKey.objects.filter(key=key).values("sha256").first()
        return row["sha256"] if row else None

    def cache_put(self, key: str, sha: str, tool: str, version: str) -> None:
        self.m.CacheKey.objects.update_or_create(
            key=key,
            defaults={
                "sha256": sha,
                "tool": tool,
                "tool_version": version,
                "created_at": now(),
            },
        )

    # creative records -------------------------------------------------

    def put_idea(self, slug: str, record: dict) -> None:
        self.m.Idea.objects.update_or_create(
            slug=slug,
            defaults={
                "sentence": record["sentence"],
                "insight": record["insight"],
                "goal": record["goal"],
                "score": float(record["score"]),
                "citations_json": json.dumps(record.get("citations") or []),
                "alternatives_json": json.dumps(record.get("alternatives") or []),
                "adversarial_json": json.dumps(record.get("adversarial") or {}),
                "created_at": now(),
            },
        )

    def get_idea(self, slug: str) -> dict | None:
        row = self.m.Idea.objects.filter(slug=slug).values().first()
        if not row:
            return None
        row["citations"] = json.loads(row.pop("citations_json") or "[]")
        row["alternatives"] = json.loads(row.pop("alternatives_json") or "[]")
        row["adversarial"] = json.loads(row.pop("adversarial_json") or "{}")
        return row

    def put_hooks(self, slug: str, rows: list[dict]) -> None:
        self.m.Hook.objects.filter(slug=slug).delete()
        self.m.Hook.objects.bulk_create(
            [
                self.m.Hook(
                    slug=slug,
                    idx=index,
                    archetype=row["archetype"],
                    spoken=row["spoken"],
                    first_frame=row["first_frame"],
                    overlay=row["overlay"],
                    chosen=bool(row.get("chosen")),
                    objection=row.get("objection"),
                    answer=row.get("answer"),
                )
                for index, row in enumerate(rows)
            ]
        )

    def get_hooks(self, slug: str) -> list[dict]:
        return list(self.m.Hook.objects.filter(slug=slug).order_by("idx").values())

    def put_beats(self, slug: str, rows: list[dict]) -> None:
        self.m.Beat.objects.filter(slug=slug).delete()
        self.m.Beat.objects.bulk_create(
            [
                self.m.Beat(
                    slug=slug,
                    idx=index,
                    name=row["name"],
                    purpose=row["purpose"],
                    overlay=row["overlay"],
                    visual_beat=row["visual_beat"],
                    seconds_est=float(row["seconds_est"]),
                )
                for index, row in enumerate(rows)
            ]
        )

    def get_beats(self, slug: str) -> list[dict]:
        return list(self.m.Beat.objects.filter(slug=slug).order_by("idx").values())

    def delete_creative_from(self, slug: str, step: str) -> None:
        order = ["idea", "hook", "board"]
        if step not in order:
            return
        if order.index(step) <= 0:
            self.m.Idea.objects.filter(slug=slug).delete()
        if order.index(step) <= 1:
            self.m.Hook.objects.filter(slug=slug).delete()
        if order.index(step) <= 2:
            self.m.Beat.objects.filter(slug=slug).delete()

    # cues and renders -------------------------------------------------

    def put_cues(self, slug: str, cues: list[dict]) -> None:
        self.m.Cue.objects.filter(slug=slug).delete()
        self.m.Cue.objects.bulk_create(
            [
                self.m.Cue(
                    slug=slug,
                    idx=index,
                    scene=cue["scene"],
                    start_s=cue["start"],
                    end_s=cue["end"],
                    text=cue["text"],
                )
                for index, cue in enumerate(cues)
            ]
        )

    def get_cues(self, slug: str) -> list[dict]:
        return list(
            self.m.Cue.objects.filter(slug=slug).order_by("idx").values()
        )

    def put_render(self, slug: str, render: dict) -> None:
        self.m.Render.objects.create(
            id=new_id(),
            slug=slug,
            sha256=render["sha256"],
            duration_s=render.get("duration_s"),
            fps=render.get("fps"),
            loudness=render.get("loudness"),
            peak=render.get("peak"),
            verified_at=render.get("verified_at"),
        )

    def get_render(self, slug: str) -> dict | None:
        return (
            self.m.Render.objects.filter(slug=slug)
            .order_by("-verified_at")
            .values()
            .first()
        )
