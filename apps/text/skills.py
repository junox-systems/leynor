"""Skill files: path resolution and the text one agent prompt needs."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "skills"
MAX_FILE_CHARS = 20000


def skill_paths(names: Sequence[str]) -> list[Path]:
    return [ROOT / name for name in names]


def missing(names: Sequence[str]) -> list[str]:
    return [str(path) for path in skill_paths(names) if not path.exists()]


def read(names: Sequence[str]) -> str:
    """Concatenated skill text, in the order given. Missing files are skipped."""
    parts = []
    for path in skill_paths(names):
        if not path.exists():
            continue
        text = path.read_text()[:MAX_FILE_CHARS]
        parts.append(f"# {path.relative_to(ROOT)}\n\n{text}")
    return "\n\n---\n\n".join(parts)
