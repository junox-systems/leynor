import hashlib

import pytest

from apps.runs.artifacts import (
    ArtifactMissing,
    FileStore,
    UnsafePath,
    artifact_key,
    safe_key,
)


def test_put_returns_sha_and_get_reads_bytes(tmp_path):
    store = FileStore(tmp_path)
    payload = "<p>hi</p>"
    sha = store.put("run/a.html", payload)

    assert sha == hashlib.sha256(payload.encode()).hexdigest()
    assert store.get("run/a.html") == payload.encode()


def test_put_creates_nested_directories(tmp_path):
    store = FileStore(tmp_path)
    store.put("org/project/run/deep/file.txt", "x")
    assert (tmp_path / "org/project/run/deep/file.txt").read_text() == "x"


def test_put_overwrites_atomically(tmp_path):
    store = FileStore(tmp_path)
    store.put("a.txt", "first")
    store.put("a.txt", "second")

    assert store.get("a.txt") == b"second"
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".tmp-")] == []


def test_get_missing_raises(tmp_path):
    with pytest.raises(ArtifactMissing):
        FileStore(tmp_path).get("nope.txt")


def test_delete_is_idempotent(tmp_path):
    store = FileStore(tmp_path)
    store.put("a.txt", "x")
    store.delete("a.txt")
    store.delete("a.txt")
    assert not (tmp_path / "a.txt").exists()


@pytest.mark.parametrize(
    "key",
    ["../escape.txt", "run/../../escape.txt", "/etc/passwd", ""],
)
def test_rejects_unsafe_keys(tmp_path, key):
    with pytest.raises(UnsafePath):
        FileStore(tmp_path).put(key, "x")


def test_rejects_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafePath):
        FileStore(root).put("link/escape.txt", "x")


def test_tmpdir_is_removed_after_use(tmp_path):
    store = FileStore(tmp_path)
    with store.tmpdir() as scratch:
        written = scratch / "a.txt"
        written.write_text("x")
    assert not written.exists()


def test_artifact_key_is_scoped_to_org_project_campaign_unit_run():
    assert (
        artifact_key("org", "proj", "camp", "reel", "run", "cues.json")
        == "org/proj/camp/reel/run/cues.json"
    )


def test_artifact_key_rejects_unsafe_name():
    with pytest.raises(UnsafePath):
        artifact_key("org", "proj", "camp", "reel", "run", "../../etc/passwd")


def test_safe_key_keeps_relative_parts():
    assert safe_key("a/b/c.txt").as_posix() == "a/b/c.txt"
