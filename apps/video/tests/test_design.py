"""The frame tokens are normative: compose reads them, never invents them."""

from apps.video.design import default_frame, parse_frame


def test_frame_roundtrip_and_defaults():
    design = parse_frame(default_frame())
    assert design.accent == "#e0a33e"
    assert design.caption_bottom == "30%"
    assert parse_frame(None).caption_bottom == "30%"


def test_frame_tokens_are_overridable():
    custom = parse_frame('---\npalette_accent: "#ff0000"\ncaption_bottom: "22%"\n---\n')
    assert custom.accent == "#ff0000"
    assert custom.caption_bottom == "22%"
