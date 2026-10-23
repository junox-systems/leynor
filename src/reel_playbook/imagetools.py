"""ImageTools: deterministic visuals with no license and no network.

A  procedural  -> transparency-friendly SVG texture, seeded by project/scene/tool
A+ waveform    -> PNG strip cut from the episode master, so it is truthful
B  stock / ai  -> later, behind the same interface and the same credits gate
"""

from __future__ import annotations

import hashlib
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .content import SceneSpec

VERSION = "1.0.0"


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

    def render(self, slug: str, scene: SceneSpec, index: int) -> Visual:
        seed = seed_for(slug, index, self.name)
        rng = random.Random(seed)
        width, height = 1080, 1920
        dots = []
        for row in range(18):
            for col in range(10):
                cx = 90 + col * 100 + rng.randint(-18, 18)
                cy = 140 + row * 100 + rng.randint(-18, 18)
                radius = rng.choice([2, 3, 4, 6, 8])
                opacity = round(rng.uniform(0.05, 0.16), 3)
                dots.append(
                    f'<circle cx="{cx}" cy="{cy}" r="{radius}" '
                    f'fill="#e0a33e" opacity="{opacity}"/>'
                )
        arc = rng.randint(280, 520)
        lines = []
        for n in range(3):
            y = 1180 + n * 130 + rng.randint(-30, 30)
            w = rng.randint(300, 760)
            lines.append(
                f'<rect x="82" y="{y}" width="{w}" height="2" '
                f'fill="#f2efe6" opacity="0.10"/>'
            )
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<circle cx="{width - 120}" cy="{arc}" r="{rng.randint(200, 340)}" fill="none" stroke="#e0a33e" stroke-width="2" opacity="0.16"/>
<circle cx="{width - 120}" cy="{arc}" r="{rng.randint(90, 180)}" fill="none" stroke="#f2efe6" stroke-width="1" opacity="0.10"/>
{''.join(dots)}
{''.join(lines)}
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
        self, slug: str, index: int, master: Path, start: float, end: float, scratch: Path
    ) -> Visual:
        seed = seed_for(slug, index, self.name)
        out = scratch / f"wave-{index:02d}.png"
        span = max(0.2, end - start)
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-ss", f"{start:.3f}", "-t", f"{span:.3f}",
                "-i", str(master),
                "-filter_complex",
                "showwavespic=s=920x260:colors=#e0a33e:scale=sqrt",
                "-frames:v", "1", str(out),
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
