"""Creative gates: steps 1-3 have to prove quality, not existence.

Each validator returns a list of failures. A non-empty list stops the build, so
these records cannot be manufactured by the pipeline from a spec file.
"""

from __future__ import annotations

import re

from .content import ReelSpec

GOALS = {"saves", "shares", "follows"}
ARCHETYPES = {
    "number-first",
    "contrarian",
    "relatable",
    "confession",
    "listicle",
    "before-after",
    "myth-buster",
    "framework",
    "pattern-interrupt",
    "how-i",
}
WORDS_PER_SECOND = 2.5


def validate_idea(record: dict | None) -> list[str]:
    if not record:
        return ["no idea record; run `reel idea <slug> --file idea.json`"]
    problems: list[str] = []
    sentence = (record.get("sentence") or "").strip()
    insight = (record.get("insight") or "").strip()
    if not 20 <= len(sentence) <= 180:
        problems.append("idea sentence must be 20-180 characters")
    if " wants " not in f" {insight.lower()} ":
        problems.append("insight must name what the audience wants")
    if " but " not in f" {insight.lower()} ":
        problems.append("insight must name what stands in the way (but ...)")
    if " because " not in f" {insight.lower()} ":
        problems.append("insight must give the reason (because ...)")
    if record.get("goal") not in GOALS:
        problems.append("goal must be saves, shares or follows")
    score = float(record.get("score") or 0)
    if not 0 <= score <= 10:
        problems.append("score must be 0-10")
    if score < 7:
        problems.append(f"score {score} is below the gate of 7")
    citations = record.get("citations") or []
    if not citations:
        problems.append("at least one citation is required")
    for index, citation in enumerate(citations, start=1):
        if not str(citation.get("claim", "")).strip():
            problems.append(f"citation {index} has no claim")
        if not str(citation.get("source", "")).strip():
            problems.append(f"citation {index} has no source")
    alternatives = record.get("alternatives") or []
    if len(alternatives) < 2:
        problems.append("record at least two rejected concepts")
    for index, alternative in enumerate(alternatives, start=1):
        if not str(alternative.get("title", "")).strip():
            problems.append(f"alternative {index} has no title")
        if not str(alternative.get("rejected", "")).strip():
            problems.append(f"alternative {index} has no rejection reason")
    adversarial = record.get("adversarial") or {}
    if not str(adversarial.get("objection", "")).strip():
        problems.append("adversarial pass needs the strongest objection")
    if not str(adversarial.get("answer", "")).strip():
        problems.append("adversarial pass needs an answer to the objection")
    return problems


def validate_hooks(rows: list[dict]) -> list[str]:
    if not rows:
        return ["no hook record; run `reel hook <slug> --file hooks.json`"]
    problems: list[str] = []
    if len(rows) < 6:
        problems.append(f"{len(rows)} hooks is under the floor of 6")
    archetypes = {row.get("archetype") for row in rows}
    unknown = archetypes - ARCHETYPES
    if unknown:
        problems.append(f"unknown archetypes: {', '.join(sorted(unknown))}")
    if len(archetypes) < 3:
        problems.append("use at least three archetypes")
    chosen = [row for row in rows if row.get("chosen")]
    if len(chosen) != 1:
        problems.append(f"exactly one hook must be chosen, got {len(chosen)}")
    for index, row in enumerate(rows, start=1):
        for field in ("spoken", "first_frame", "overlay"):
            if not str(row.get(field, "")).strip():
                problems.append(f"hook {index} is missing {field}")
        overlay = str(row.get("overlay", "")).strip()
        words = len(overlay.split())
        if overlay and not 3 <= words <= 7:
            problems.append(f"hook {index} overlay is {words} words, needs 3-7")
        if len(overlay) > 44:
            problems.append(f"hook {index} overlay is over 44 characters")
    if chosen:
        winner = chosen[0]
        if not str(winner.get("objection", "")).strip():
            problems.append("winning hook needs the objection against it")
        if not str(winner.get("answer", "")).strip():
            problems.append("winning hook needs the answer that beats the objection")
    return problems


def validate_beats(rows: list[dict], spec: ReelSpec) -> list[str]:
    if not rows:
        return ["no beat plan; run `reel board <slug> --file beats.json`"]
    problems: list[str] = []
    if len(rows) != len(spec.scenes):
        problems.append(
            f"{len(rows)} beats for {len(spec.scenes)} scenes; they must match"
        )
    purposes = [str(row.get("purpose", "")).strip().lower() for row in rows]
    if not purposes or purposes[0] != "hook":
        problems.append("the first beat must be the hook")
    if "turn" not in purposes:
        problems.append("the plan needs a turn")
    if "payoff" not in purposes:
        problems.append("the plan needs a payoff")
    if purposes.count("payoff") > 1:
        problems.append("only one beat can be the payoff")
    for index, row in enumerate(rows, start=1):
        if not str(row.get("name", "")).strip():
            problems.append(f"beat {index} has no name")
        if not str(row.get("visual_beat", "")).strip():
            problems.append(f"beat {index} has no visual beat")
        if float(row.get("seconds_est") or 0) <= 0:
            problems.append(f"beat {index} has no estimated length")
    for index, (row, scene) in enumerate(zip(rows, spec.scenes), start=1):
        if str(row.get("overlay", "")).strip() != scene.overlay:
            problems.append(f"beat {index} overlay does not match the spec scene")
    estimate = sum(len(scene.narration.split()) for scene in spec.scenes) / WORDS_PER_SECOND
    planned = sum(float(row.get("seconds_est") or 0) for row in rows)
    if estimate and not 0.75 * estimate <= planned <= 1.25 * estimate:
        problems.append(
            f"planned {planned:.1f}s is outside 25% of the {estimate:.1f}s script"
        )
    return problems


def citation_map(record: dict) -> dict[str, str]:
    return {
        str(item.get("claim", "")).strip(): str(item.get("source", "")).strip()
        for item in record.get("citations") or []
    }


def overlay_words(text: str) -> int:
    return len(re.findall(r"\S+", text))
