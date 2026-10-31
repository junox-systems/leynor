"""The look, as input: `frame.md` frontmatter is the design spec.

Tokens are normative. `compose` reads them; it does not invent colors. The
prose below the frontmatter is context for a person, not for the renderer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Design:
    bg: str = "#0d0c0a"
    fg: str = "#f4efe4"
    accent: str = "#e0a33e"
    dim: str = "#9a9182"
    line: str = "rgba(244,239,228,0.14)"
    font_display: str = '"Helvetica Neue", Arial, sans-serif'
    font_mono: str = '"Courier New", monospace'
    caption_bottom: str = "30%"
    caption_size: int = 47

    def tokens(self) -> dict:
        return {
            "palette_bg": self.bg,
            "palette_fg": self.fg,
            "palette_accent": self.accent,
            "palette_dim": self.dim,
            "palette_line": self.line,
            "font_display": self.font_display,
            "font_mono": self.font_mono,
            "caption_bottom": self.caption_bottom,
            "caption_size": self.caption_size,
        }


DEFAULTS = Design()
KEYS = {
    "palette_bg": "bg",
    "palette_fg": "fg",
    "palette_accent": "accent",
    "palette_dim": "dim",
    "palette_line": "line",
    "font_display": "font_display",
    "font_mono": "font_mono",
    "caption_bottom": "caption_bottom",
    "caption_size": "caption_size",
}


def parse_frame(text: str | None) -> Design:
    if not text:
        return Design()
    values = Design().tokens()
    block = text.split("---", 2)
    if len(block) < 3:
        return Design()
    for line in block[1].splitlines():
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key, raw = key.strip(), raw.strip().strip('"').strip("'")
        field = KEYS.get(key)
        if field is None:
            continue
        values[key] = int(raw) if field == "caption_size" else raw
    return Design(**{field: values[key] for key, field in KEYS.items()})


def default_frame(design: Design | None = None) -> str:
    design = design or Design()
    tokens = "\n".join(
        f"{key}: {value}" if not isinstance(value, str) else f'{key}: "{value}"'
        for key, value in design.tokens().items()
    )
    return f"""---
{tokens}
---

# FRAME

- size: 1080x1920, 30 fps
- ground: warm near-black, tinted toward the accent
- type: heavy grotesque display, monospace metadata, no second sans
- captions: {design.caption_bottom} up from the bottom, centred, 90 px side margins
- components: plate, veil, glow, grain, ghost label, oversized numeral, grid, rules
- five layout variants; no two adjacent scenes share one
- decoratives keep ambient motion for the whole scene

A change to a token here changes every composition. Do not hardcode colours in
`compose.py`.
"""
