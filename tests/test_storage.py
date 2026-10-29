"""Storage: one workspace, no escape, blobs deduped in Postgres."""

import pytest

from reel_playbook.storage import SLUG, Workspace


def test_workspace_layout_and_db_url(tmp_path):
    ws = Workspace(tmp_path / "ws")
    assert ws.projects.is_dir() and ws.tmp.is_dir()
    assert ws.db_url.startswith("postgresql://")
    assert ws.db_url.endswith("/reel_test")


def test_assert_inside_rejects_outside(tmp_path):
    ws = Workspace(tmp_path / "ws")
    with pytest.raises(ValueError):
        ws.assert_inside(tmp_path / "elsewhere" / "x.png")
    inside = ws.project_dir("abc")
    assert ws.assert_inside(inside) == inside.resolve()


def test_slug_validation(tmp_path):
    ws = Workspace(tmp_path / "ws")
    with pytest.raises(ValueError):
        ws.project_dir("../escape")
    assert SLUG.match("04-five-minutes")


def test_blob_is_content_addressed(tmp_path):
    ws = Workspace(tmp_path / "ws")
    catalog = ws.catalog()
    first = catalog.put_blob(b"same bytes", "txt", "file")
    second = catalog.put_blob(b"same bytes", "txt", "file")
    assert first == second
    assert catalog.get_blob(first)["data"] == b"same bytes"


def test_two_projects_share_one_blob(tmp_path):
    ws = Workspace(tmp_path / "ws")
    catalog = ws.catalog()
    sha = catalog.put_blob(b"shared", "svg", "visual")
    for slug in ("aa", "bb"):
        catalog.put_artifact(slug, "assets/visuals/s1.svg", sha256=sha, kind="visual")
    from reel_playbook.db import models

    assert models.Blob.objects.count() == 1
    assert catalog.get_artifact("aa", "assets/visuals/s1.svg")["sha256"] == sha


def test_artifact_text_and_bytes(tmp_path):
    ws = Workspace(tmp_path / "ws")
    catalog = ws.catalog()
    catalog.put_artifact("aa", "STORYBOARD.md", text="# STORYBOARD\n")
    catalog.put_artifact("aa", "captions.json", text="{}")
    assert catalog.artifact_bytes("aa", "STORYBOARD.md") == b"# STORYBOARD\n"
    assert {row["path"] for row in catalog.list_artifacts("aa")} == {
        "STORYBOARD.md",
        "captions.json",
    }
    catalog.delete_artifact("aa", "captions.json")
    assert catalog.get_artifact("aa", "captions.json") is None


def test_cache_key_roundtrip(tmp_path):
    ws = Workspace(tmp_path / "ws")
    store, catalog = ws.store(), ws.catalog()
    key = store.key("procedural", "1.0.0", 7, 2)
    sha = catalog.put_blob(b"cached", "png", "visual")
    assert catalog.cache_get(key) is None
    catalog.cache_put(key, sha, "procedural", "1.0.0")
    assert catalog.cache_get(key) == sha


def test_project_upsert(tmp_path):
    ws = Workspace(tmp_path / "ws")
    catalog = ws.catalog()
    record = {
        "slug": "aa",
        "state": "IDEA",
        "version": "0.1.0",
        "root": str(ws.project_dir("aa")),
        "fps": 30,
        "width": 1080,
        "height": 1920,
        "duration_s": None,
        "max_attempts": 3,
        "tokens_json": "{}",
        "locked_json": "{}",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    catalog.put_project(record)
    record["state"] = "HOOK"
    catalog.put_project(record)
    assert catalog.get_project("aa")["state"] == "HOOK"
    assert len(catalog.list_projects()) == 1
