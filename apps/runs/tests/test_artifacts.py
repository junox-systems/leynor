import hashlib
from unittest import mock

import pytest
from django.core.files.storage import FileSystemStorage, InMemoryStorage

from apps.runs.artifacts import ArtifactMissing, ArtifactStore, UnsafePath, safe_key


@pytest.fixture
def store():
    return ArtifactStore("org/reel", InMemoryStorage())


def test_put_returns_sha_and_get_reads_bytes(store):
    payload = "<p>hi</p>"
    sha = store.put("run/a.html", payload)

    assert sha == hashlib.sha256(payload.encode()).hexdigest()
    assert store.get("run/a.html") == payload.encode()
    assert store.sha256("run/a.html") == sha
    assert store.size("run/a.html") == len(payload)


def test_keys_live_below_the_prefix(tmp_path):
    ArtifactStore("org/reel", FileSystemStorage(tmp_path)).put("deep/file.txt", "x")
    assert (tmp_path / "org/reel/deep/file.txt").read_text() == "x"


@pytest.mark.parametrize("storage", [InMemoryStorage, FileSystemStorage])
def test_put_overwrites_in_place(storage, tmp_path):
    store = ArtifactStore("reel", storage(location=str(tmp_path)))
    store.put("a.txt", "first")
    store.put("a.txt", "second")

    assert store.get("a.txt") == b"second"
    assert store.storage.listdir("reel") == ([], ["a.txt"])


class OverwritingStorage(InMemoryStorage):
    file_overwrite = True  # like S3Storage

    def get_available_name(self, name, max_length=None):
        return name


def test_a_failed_overwrite_keeps_the_old_file():
    store = ArtifactStore("reel", OverwritingStorage())
    store.put("out.mp4", "old")
    with (
        mock.patch.object(store.storage, "_save", side_effect=OSError("upload failed")),
        pytest.raises(OSError),
    ):
        store.put("out.mp4", "new")
    assert store.get("out.mp4") == b"old"


def test_read_range_reads_only_those_bytes(store):
    store.put("out.mp4", "0123456789")
    assert store.read_range("out.mp4", 2, 5) == b"2345"


def test_read_range_asks_s3_for_the_range_only():
    obj = mock.Mock()
    obj.get.return_value = {"Body": mock.Mock(read=lambda: b"2345")}
    storage = mock.Mock(_normalize_name=lambda name: name)
    storage.bucket.Object.return_value = obj

    assert ArtifactStore("reel", storage).read_range("out.mp4", 2, 5) == b"2345"
    storage.bucket.Object.assert_called_once_with("reel/out.mp4")
    obj.get.assert_called_once_with(Range="bytes=2-5")


def test_get_missing_raises(store):
    with pytest.raises(ArtifactMissing):
        store.get("nope.txt")


def test_delete_is_idempotent(store):
    store.put("a.txt", "x")
    store.delete("a.txt")
    store.delete("a.txt")
    assert not store.exists("a.txt")


def test_delete_all_removes_only_this_prefix():
    storage = InMemoryStorage()
    mine, other = ArtifactStore("org/one", storage), ArtifactStore("org/two", storage)
    mine.put("assets/visuals/s1.svg", "x")
    mine.put("out.mp4", "y")
    other.put("out.mp4", "z")

    mine.delete_all()
    mine.delete_all()  # nothing left: still fine

    assert not mine.exists("out.mp4") and not mine.exists("assets/visuals/s1.svg")
    assert other.get("out.mp4") == b"z"


def test_delete_all_refuses_an_empty_prefix():
    with pytest.raises(UnsafePath):
        ArtifactStore("", InMemoryStorage()).delete_all()


@pytest.mark.parametrize(
    "key",
    ["../escape.txt", "run/../../escape.txt", "/etc/passwd", ""],
)
def test_rejects_unsafe_keys(store, key):
    with pytest.raises(UnsafePath):
        store.put(key, "x")


def test_tmpdir_is_removed_after_use(store):
    with store.tmpdir() as scratch:
        written = scratch / "a.txt"
        written.write_text("x")
    assert not written.exists()


def test_safe_key_keeps_relative_parts():
    assert safe_key("a/b/c.txt").as_posix() == "a/b/c.txt"
