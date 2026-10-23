"""Storage: one workspace, no escape, dedupe by content."""

import pytest

from reel_playbook.storage import SLUG, Catalog, Store, Workspace


def test_workspace_layout(tmp_path):
    ws = Workspace(tmp_path / "ws")
    assert ws.db_path.name == "reel.sqlite"
    assert ws.blobs.is_dir() and ws.projects.is_dir() and ws.tmp.is_dir()


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
    store = ws.store()
    first, ref = store.put_bytes(b"same bytes", "txt")
    second, again = store.put_bytes(b"same bytes", "txt")
    assert first == second
    assert ref == again
    assert store.path(ref).read_bytes() == b"same bytes"


def test_two_projects_share_one_blob(tmp_path):
    ws = Workspace(tmp_path / "ws")
    store = ws.store()
    catalog = ws.catalog()
    sha, _ = store.put_bytes(b"shared", "svg")
    for slug in ("aa", "bb"):
        catalog.put_asset(
            {
                "sha256": sha,
                "ext": "svg",
                "kind": "visual",
                "media_type": "image/svg+xml",
                "bytes": 6,
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
        catalog.link_asset(slug, sha, "visual:s1", {})
    blobs = [path for path in (ws.blobs).rglob("*") if path.is_file()]
    assert len(blobs) == 1
    assert len(catalog.get_assets("aa")) == 1


def test_cache_key_roundtrip(tmp_path):
    ws = Workspace(tmp_path / "ws")
    store, catalog = ws.store(), ws.catalog()
    key = store.key("procedural", "1.0.0", 7, 2)
    sha, _ = store.put_bytes(b"cached", "png")
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
