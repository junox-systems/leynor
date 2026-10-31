"""One frozen visual per scene, with a credits file that says how it was made.

The only scene data this engine reads is the label. Everything else is the
slug and the scene number, so the same call serves any channel.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from apps.image.tools import Procedural


class Labelled(Protocol):
    label: str


class ImageError(RuntimeError):
    pass


def generate(slug: str, scenes: Sequence[Labelled], store, *, tool=None) -> list[dict]:
    """Render every scene into the store and return one row per visual."""
    tool = tool or Procedural()
    written = []
    for index, scene in enumerate(scenes, start=1):
        visual = tool.render(slug, scene.label, index)
        key = f"assets/visuals/s{index}.{visual.ext}"
        sha = store.put(key, visual.data)
        written.append(
            {
                "index": index,
                "key": key,
                "sha": sha,
                "tool": visual.tool,
                "tool_version": visual.tool_version,
                "seed": visual.seed,
            }
        )

    credits = [
        "# CREDITS",
        "",
        "All visuals generated locally. No third-party media.",
        "",
    ]
    credits += [
        f"- s{row['index']}: {row['tool']} {row['tool_version']}, "
        f"seed {row['seed']}, {row['sha'][:12]}"
        for row in written
    ]
    store.put("assets/CREDITS.md", "\n".join(credits) + "\n")
    return written
