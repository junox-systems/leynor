import json

import pytest
from pydantic import ValidationError

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


def test_spec_rejects_duration_outside_window():
    with pytest.raises(ValidationError):
        _spec(target_seconds=30)


def test_script_and_sentences():
    spec = _spec()
    assert spec.script() == "One line.\nTwo lines here."
    assert [scene for scene, _ in spec.sentences()] == [1, 2]


def test_load_spec_roundtrip(tmp_path):
    spec = _spec()
    path = tmp_path / "ep-01.json"
    path.write_text(json.dumps(spec.model_dump()))
    assert load_spec(path).slug == "ep-01"
