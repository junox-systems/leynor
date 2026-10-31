"""The image engine: one frozen visual per scene, plus credits."""

from dataclasses import dataclass

from apps.image import services
from apps.image.tools import Procedural, catalogue
from apps.runs.artifacts import FileStore


@dataclass
class Scene:
    label: str


def test_generate_writes_one_visual_per_scene_and_credits(tmp_path):
    store = FileStore(tmp_path)
    written = services.generate("ep-image", [Scene("a"), Scene("b")], store)

    assert [row["index"] for row in written] == [1, 2]
    for row in written:
        assert store.get(row["key"])
        assert len(row["sha"]) == 64
    assert store.get("assets/CREDITS.md").decode().count("All visuals generated locally")


def test_generate_is_deterministic(tmp_path):
    first = FileStore(tmp_path / "one")
    second = FileStore(tmp_path / "two")
    scenes = [Scene("a")]
    a = services.generate("ep-image", scenes, first)
    b = services.generate("ep-image", scenes, second)

    assert first.get(a[0]["key"]) == second.get(b[0]["key"])
    assert a[0]["seed"] == b[0]["seed"]


def test_generate_accepts_an_injected_tool(tmp_path):
    store = FileStore(tmp_path)
    written = services.generate("ep-image", [Scene("a")], store, tool=Procedural())

    assert written[0]["tool"] == "procedural"


def test_catalogue_lists_every_tool():
    names = {row["name"] for row in catalogue()}
    assert names == {"procedural", "waveform"}
