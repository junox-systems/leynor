"""Image tools: deterministic visuals with no license and no network.

A  procedural  -> transparency-friendly SVG texture, seeded by slug/scene/tool
A+ waveform    -> PNG strip cut from the episode master, so it is truthful
B  stock / ai  -> later, behind the same interface and the same credits gate

Only channel-agnostic inputs cross this boundary: a slug, a scene number, a
label. The engine never imports a spec, a channel, or an ORM model.
"""

from __future__ import annotations

import hashlib
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "1.1.0"


@dataclass
class Visual:
    ext: str
    media_type: str
    data: bytes
    tool: str
    tool_version: str
    seed: int
    meta: dict = field(default_factory=dict)


def seed_for(slug: str, scene: int, tool: str) -> int:
    raw = f"{slug}:{scene}:{tool}:{VERSION}".encode()
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


class Procedural:
    name = "procedural"
    version = VERSION

    def render(self, slug: str, label: str, index: int) -> Visual:
        # The label is carried for tools that read text (stock, AI); this one
        # seeds on slug, index and tool so output stays reproducible.
        seed = seed_for(slug, index, self.name)
        rng = random.Random(seed)
        width, height = 1080, 1920
        dots = []
        for row in range(18):
            for col in range(10):
                cx = 90 + col * 100 + rng.randint(-18, 18)
                cy = 140 + row * 100 + rng.randint(-18, 18)
                radius = rng.choice([3, 4, 6, 9, 12])
                opacity = round(rng.uniform(0.10, 0.32), 3)
                dots.append(
                    f'<circle cx="{cx}" cy="{cy}" r="{radius}" '
                    f'fill="#e0a33e" opacity="{opacity}"/>'
                )
        arc = rng.randint(280, 520)
        rings = []
        for n, radius in enumerate(
            (rng.randint(380, 520), rng.randint(240, 360), rng.randint(120, 200))
        ):
            rings.append(
                f'<circle cx="{width - 110}" cy="{arc}" r="{radius}" fill="none" '
                f'stroke="#e0a33e" stroke-width="{2 - n * 0.4}" '
                f'opacity="{0.26 - n * 0.06}"/>'
            )
        hatch = []
        for n in range(14):
            x = 40 + n * 78 + rng.randint(-10, 10)
            hatch.append(
                f'<line x1="{x}" y1="1180" x2="{x + 260}" y2="1700" '
                f'stroke="#f4efe4" stroke-width="1" opacity="0.05"/>'
            )
        lines = []
        for n in range(3):
            y = 1180 + n * 150 + rng.randint(-30, 30)
            w = rng.randint(360, 820)
            lines.append(
                f'<rect x="96" y="{y}" width="{w}" height="1.5" '
                f'fill="#f4efe4" opacity="0.12"/>'
            )
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs>
  <radialGradient id="wash" cx="78%" cy="18%" r="80%">
    <stop offset="0%" stop-color="#3a2c14" stop-opacity="0.55"/>
    <stop offset="55%" stop-color="#16130e" stop-opacity="0.85"/>
    <stop offset="100%" stop-color="#0d0c0a" stop-opacity="1"/>
  </radialGradient>
  <linearGradient id="low" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#0d0c0a" stop-opacity="0"/>
    <stop offset="100%" stop-color="#0d0c0a" stop-opacity="0.9"/>
  </linearGradient>
</defs>
<rect width="{width}" height="{height}" fill="url(#wash)"/>
{"".join(rings)}
{"".join(hatch)}
{"".join(dots)}
{"".join(lines)}
<rect y="{height - 700}" width="{width}" height="700" fill="url(#low)"/>
</svg>
"""
        return Visual(
            ext="svg",
            media_type="image/svg+xml",
            data=svg.encode(),
            tool=self.name,
            tool_version=self.version,
            seed=seed,
            meta={"scene": index},
        )


class Waveform:
    """Cut a strip from the real master. Needs ffmpeg, runs after C5."""

    name = "waveform"
    version = VERSION

    def render(
        self,
        slug: str,
        index: int,
        master: Path,
        start: float,
        end: float,
        scratch: Path,
    ) -> Visual:
        seed = seed_for(slug, index, self.name)
        out = scratch / f"wave-{index:02d}.png"
        span = max(0.2, end - start)
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{span:.3f}",
                "-i",
                str(master),
                "-filter_complex",
                "showwavespic=s=920x260:colors=#e0a33e:scale=sqrt",
                "-frames:v",
                "1",
                str(out),
            ],
            check=True,
        )
        return Visual(
            ext="png",
            media_type="image/png",
            data=out.read_bytes(),
            tool=self.name,
            tool_version=self.version,
            seed=seed,
            meta={"scene": index, "start": round(start, 3), "end": round(end, 3)},
        )


def get(name: str):
    tools = {tool.name: tool for tool in (Procedural(), Waveform())}
    if name not in tools:
        raise KeyError(f"unknown ImageTool {name!r}; one of {', '.join(tools)}")
    return tools[name]


def catalogue() -> list[dict]:
    return [
        {"name": tool.name, "version": tool.version, "class": type(tool).__name__}
        for tool in (Procedural(), Waveform())
    ]
