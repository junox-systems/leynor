"""Skill paths for a step, and the text an agent needs to follow them."""

from __future__ import annotations

from pathlib import Path

from .steps import StepSpec

ROOT = Path(__file__).resolve().parents[2] / "skills"
MAX_FILE_CHARS = 20000


def skill_paths(step: StepSpec, *, optional: bool = False) -> list[Path]:
    names = step.optional_skills if optional else step.skills
    return [ROOT / name for name in names]


def missing(step: StepSpec, *, optional: bool = False) -> list[str]:
    return [str(path) for path in skill_paths(step, optional=optional) if not path.exists()]


def read(step: StepSpec, *, optional: bool = False) -> str:
    """Concatenated must-read docs for a drafting prompt."""
    parts = []
    paths = skill_paths(step) + (skill_paths(step, optional=True) if optional else [])
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text()[:MAX_FILE_CHARS]
        parts.append(f"# {path.relative_to(ROOT)}\n\n{text}")
    return "\n\n---\n\n".join(parts)
