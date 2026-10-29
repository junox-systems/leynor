"""App import graph: one direction, no cycles, no dead engine package."""

import ast
from pathlib import Path

APPS = Path(__file__).resolve().parents[1] / "apps"
CONTEXTS = ("projects", "runs", "creative", "voices", "renders")

ALLOWED = {
    # shared kernel: spec, steps, gates
    "projects": set(),
    "creative": {"projects"},
    "voices": {"projects"},
    "renders": {"projects", "voices"},
    "runs": {"projects", "creative", "voices", "renders"},
}


def imported_apps(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == "apps" and len(parts) > 1 and parts[1] in CONTEXTS:
                found.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "apps" and len(parts) > 1 and parts[1] in CONTEXTS:
                    found.add(parts[1])
    return found


def python_files(context: str) -> list[Path]:
    # Tests import across contexts on purpose: they are the place where a fake
    # from another context is wired in.
    return [
        path
        for path in (APPS / context).rglob("*.py")
        if "__pycache__" not in path.parts and "tests" not in path.parts
    ]


def test_context_imports_follow_the_declared_direction():
    violations = []
    for context in CONTEXTS:
        for path in python_files(context):
            for imported in imported_apps(path):
                if imported == context or imported in ALLOWED[context]:
                    continue
                violations.append(
                    f"{path.relative_to(APPS.parent)} imports apps.{imported}"
                )
    assert violations == [], "\n".join(violations)


def test_no_app_imports_the_old_engine_package():
    offenders = [
        str(path)
        for context in CONTEXTS
        for path in python_files(context)
        if "reel_playbook" in path.read_text()
    ]
    assert offenders == []


def test_renders_never_imports_voices_models():
    for path in python_files("renders"):
        text = path.read_text()
        assert "apps.voices.models" not in text, path
