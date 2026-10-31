"""Content specs and composition contract."""

import json
import re

import pytest
from pydantic import ValidationError

from apps.video.compose import compose, scene_windows
from apps.video.spec import ReelSpec, load_spec


def _spec(**overrides) -> ReelSpec:
    base = {
        "slug": "ep-01",
        "title": "Ep 01",
        "scenes": [
            {"narration": "One line.", "overlay": "One", "label": "first"},
            {"narration": "Two lines here.", "overlay": "Two", "label": "second"},
        ],
    }
    base.update(overrides)
    return ReelSpec(**base)


@pytest.fixture
def spec():
    return _spec()


@pytest.fixture
def cues():
    return [
        {"scene": 1, "start": 0.12, "end": 3.0, "text": "One line."},
        {"scene": 2, "start": 3.4, "end": 6.0, "text": "Two lines here."},
    ]


def test_spec_rejects_long_overlay():
    with pytest.raises(ValidationError):
        ReelSpec(
            slug="ep-01",
            title="t",
            scenes=[
                {"narration": "a.", "overlay": "x" * 45, "label": "a"},
                {"narration": "b.", "overlay": "b", "label": "b"},
            ],
        )


def test_spec_rejects_bad_slug():
    with pytest.raises(ValidationError):
        _spec(slug="../etc")


def test_spec_needs_two_scenes():
    with pytest.raises(ValidationError):
        _spec(scenes=[{"narration": "a.", "overlay": "a", "label": "a"}])


def test_script_and_sentences(spec):
    assert spec.script() == "One line.\nTwo lines here."
    assert [scene for scene, _ in spec.sentences()] == [1, 2]


def test_load_spec_roundtrip(tmp_path, spec):
    path = tmp_path / "ep-01.json"
    path.write_text(json.dumps(spec.model_dump()))
    assert load_spec(path).slug == "ep-01"


def test_scene_windows_follow_cue_starts(cues):
    windows = scene_windows(cues, 2, 6.4)
    assert windows[0][0] == 0.0
    assert windows[0][1] == pytest.approx(3.4)
    assert windows[1][1] == pytest.approx(6.4)


def test_scene_windows_never_overlap(cues):
    windows = scene_windows(cues, 2, 6.0)
    assert windows[0][1] <= windows[1][0] + 1e-9


def test_compose_writes_host_captions_and_scenes(tmp_path, spec, cues):
    written = compose(tmp_path, spec, cues, 6.4, {1: ["assets/visuals/s1.svg"]})
    index = (tmp_path / "index.html").read_text()
    assert 'data-composition-id="reel-ep-01"' in index
    assert 'window.__timelines["reel-ep-01"]' in index
    assert 'data-duration="6.4"' in index
    assert 'src="assets/voice.wav"' in index
    assert "compositions/s1.html" in index
    assert "compositions/captions.html" in index
    assert written["index"].exists()
    assert written["s1"].exists()

    captions = (tmp_path / "compositions" / "captions.html").read_text()
    assert captions.count('class="clip cue"') == 2
    assert 'data-start="0.12"' in captions

    scene = (tmp_path / "compositions" / "s1.html").read_text()
    assert "assets/visuals/s1.svg" in scene
    assert 'window.__timelines["s1"]' in scene


def test_compose_ids_match_hosts(tmp_path, spec, cues):
    compose(tmp_path, spec, cues, 6.4, {})
    index = (tmp_path / "index.html").read_text()
    ids = set(re.findall(r'data-composition-id="([^"]+)"', index))
    files = {
        f"reel-{spec.slug}",
        "captions",
        *(f"s{i}" for i in range(1, len(spec.scenes) + 1)),
    }
    assert ids == files


def test_compose_uses_design_tokens(tmp_path, spec, cues):
    from apps.video.design import Design

    compose(
        tmp_path,
        spec,
        cues,
        6.4,
        {},
        Design(bg="#101010", accent="#ff0000", caption_bottom="22%"),
    )
    scene = (tmp_path / "compositions" / "s1.html").read_text()
    assert "#ff0000" in scene
    assert "#101010" in scene
    captions = (tmp_path / "compositions" / "captions.html").read_text()
    assert "bottom:22%" in captions
