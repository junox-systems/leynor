"""hyperframes-core rules, encoded so step 4 cannot regress."""

import re

import pytest

from reel_playbook.build import BuildError, check_summary
from reel_playbook.compose import compose
from reel_playbook.content import ReelSpec

SCENES = [
    {"narration": f"Line {index} here.", "overlay": f"Overlay {index}", "label": f"label {index}"}
    for index in range(1, 6)
]
CUES = [
    {"scene": index, "start": index * 2.0, "end": index * 2.0 + 1.6,
     "text": f"Line {index} here."}
    for index in range(1, 6)
]


@pytest.fixture
def built(tmp_path):
    spec = ReelSpec(slug="ep-contract", title="Contract", scenes=SCENES)
    compose(tmp_path, spec, CUES, 12.0, {})
    return tmp_path, spec


def test_root_is_styled_by_id_not_class(built):
    root, _ = built
    index = (root / "index.html").read_text()
    tag = re.search(r'<div id="root"[^>]*>', index)
    assert tag is not None
    assert "class=" not in tag.group(0)


def test_every_gsap_target_exists(built):
    root, _ = built
    for path in sorted((root / "compositions").glob("s*.html")):
        text = path.read_text()
        ids = set(re.findall(r'id="(s\d+-[a-z]+)"', text))
        targets = set(re.findall(r'"#(s\d+-[a-z]+)"', text))
        assert targets, f"{path.name} has no tweens"
        assert targets <= ids, f"{path.name} tweens missing ids: {targets - ids}"


def test_captions_are_marked_and_clipped(built):
    root, _ = built
    index = (root / "index.html").read_text()
    assert 'data-track-kind="captions"' in index
    captions = (root / "compositions" / "captions.html").read_text()
    cues = re.findall(r"<div ([^>]*class=\"clip cue\"[^>]*)>", captions)
    assert len(cues) == len(CUES)
    for attrs in cues:
        assert 'id="cue-' in attrs


def test_type_never_goes_below_the_floor(built):
    root, _ = built
    files = list((root / "compositions").glob("*.html"))
    sizes = []
    for path in files:
        sizes += [int(size) for size in re.findall(r"font-size:(\d+)px", path.read_text())]
    assert sizes
    assert min(sizes) >= 28


def test_host_duration_matches_the_master(built):
    root, _ = built
    index = (root / "index.html").read_text()
    assert 'data-duration="12.0"' in index
    hosts = re.findall(r'data-composition-src="compositions/(s\d+)\.html"', index)
    for host in hosts:
        assert (root / "compositions" / f"{host}.html").exists()


def test_check_summary_reads_counts():
    assert check_summary("0 error(s), 0 warning(s), 20 info(s)") == (0, 0)
    assert check_summary("1 error(s), 3 warning(s)") == (1, 3)


def test_check_summary_without_a_summary_fails():
    with pytest.raises(BuildError):
        check_summary("Check passed")
