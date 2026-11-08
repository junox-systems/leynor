"""App import graph: channel to engine to store, never backwards."""

import ast
from pathlib import Path

APPS = Path(__file__).resolve().parents[1] / "apps"

CHANNELS = ("instagram", "tiktok", "twitter", "linkedin")
ENGINES = ("text", "image", "video")
CONTAINERS = ("projects", "campaigns", "brands")
STORES = ("runs",)
CONTEXTS = CONTAINERS + CHANNELS + ENGINES + STORES

ALLOWED = {
    "projects": set(),
    "campaigns": {"projects"},
    "brands": set(),
    # A channel may import the campaign layer, every engine and the store.
    "instagram": {"campaigns", "projects", "text", "image", "video", "runs"},
    "tiktok": {"campaigns"},
    "twitter": {"campaigns"},
    "linkedin": {"campaigns"},
    # Engines know no platform and no ORM model.
    "text": set(),
    "image": set(),
    "video": set(),
    "runs": set(),
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


def test_no_channel_imports_another_channel():
    violations = []
    for channel in CHANNELS:
        for path in python_files(channel):
            for imported in imported_apps(path):
                if imported in CHANNELS and imported != channel:
                    violations.append(f"{path} imports apps.{imported}")
    assert violations == [], "\n".join(violations)


def test_engines_import_no_orm_models():
    violations = []
    for engine in ENGINES:
        for path in python_files(engine):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.endswith(".models"):
                        violations.append(f"{path} imports {node.module}")
    assert violations == [], "\n".join(violations)


def test_campaigns_import_no_channel_package():
    violations = [
        str(path)
        for path in python_files("campaigns")
        for imported in imported_apps(path)
        if imported in CHANNELS
    ]
    assert violations == [], "\n".join(violations)
