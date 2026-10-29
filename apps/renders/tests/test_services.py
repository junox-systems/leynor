"""Look and print over a Store, with HyperFrames faked."""

from pathlib import Path

import pytest

from apps.projects.spec import ReelSpec
from apps.renders import services
from apps.renders.video import RenderResult, VideoError
from apps.runs.artifacts import FileStore
from apps.voices.cues import CueData


@pytest.fixture
def spec():
    return ReelSpec(
        slug="ep-renders",
        title="Renders",
        scenes=[
            {"narration": "One line.", "overlay": "One", "label": "a"},
            {"narration": "Two lines.", "overlay": "Two", "label": "b"},
        ],
    )


@pytest.fixture
def cues():
    return [
        CueData(idx=1, scene=1, start=0.1, end=1.0, text="One line."),
        CueData(idx=2, scene=2, start=1.2, end=2.0, text="Two lines."),
    ]


def test_run_look_writes_one_visual_per_scene_and_credits(tmp_path, spec):
    store = FileStore(tmp_path)
    written = services.run_look(spec, store)

    assert [row["index"] for row in written] == [1, 2]
    for row in written:
        assert store.get(row["key"])
        assert len(row["sha"]) == 64
    credits = store.get("assets/CREDITS.md").decode()
    assert "No third-party media" in credits


def test_run_compose_writes_index_and_scenes(tmp_path, spec, cues):
    store = FileStore(tmp_path)
    written = services.run_look(spec, store)
    visuals = {row["index"]: [row["key"]] for row in written}

    keys = services.run_compose(spec, cues, 2.0, visuals, store)

    assert "index.html" in keys
    assert any(key.startswith("compositions/") for key in keys)
    index = store.get("index.html").decode()
    assert 'data-composition-id="reel-ep-renders"' in index


def test_run_print_refuses_a_dirty_check(tmp_path, monkeypatch):
    store = FileStore(tmp_path)
    store.put("index.html", "<html></html>")
    monkeypatch.setattr(services, "check", lambda scratch: "2 error(s), 1 warning(s)")

    with pytest.raises(services.RenderError):
        services.run_print(store, ["index.html"])


def test_run_print_stores_the_render(tmp_path, monkeypatch):
    store = FileStore(tmp_path)
    store.put("index.html", "<html></html>")

    def fake_encode(workdir: Path, quality="delivery") -> Path:
        out = workdir / "out.mp4"
        out.write_bytes(b"mp4-bytes")
        return out

    monkeypatch.setattr(services, "check", lambda scratch: "0 error(s), 0 warning(s)")
    monkeypatch.setattr(services, "encode", fake_encode)
    monkeypatch.setattr(
        services, "fit", lambda rendered, duration, fps, scratch: rendered
    )

    result = services.run_print(store, ["index.html"], duration=2.0)

    assert isinstance(result, RenderResult)
    assert store.get("out.mp4") == b"mp4-bytes"
    assert len(result.sha256) == 64


def test_video_error_is_raised_when_hyperframes_is_missing(monkeypatch):
    from apps.renders import video

    monkeypatch.setattr(video.shutil, "which", lambda name: None)
    with pytest.raises(VideoError):
        video.npx(["check", "."], Path("."))
