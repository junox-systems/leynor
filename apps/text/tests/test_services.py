"""Drafting wiring: settings pick the model, the graph does the work."""

import pytest

from apps.text import services
from apps.text.graphs import DraftDeps
from apps.text.results import DraftResult


class FakeAgents:
    def __init__(self):
        self.deps_value = DraftDeps(
            generate=lambda brief: "d",
            critique=lambda draft: "c",
            revise=lambda draft, critique: "r",
        )

    def deps(self):
        return self.deps_value


@pytest.fixture
def captured(monkeypatch):
    calls = {}

    def fake_build_agents(model=None, skills=""):
        calls["model"] = model
        calls["skills"] = skills
        return FakeAgents()

    def fake_run_draft(brief, deps):
        calls["brief"] = brief
        calls["deps"] = deps
        return DraftResult(draft="d", critique="c", revised="r", revisions=1)

    monkeypatch.setattr(services, "build_agents", fake_build_agents)
    monkeypatch.setattr(services, "run_draft", fake_run_draft)
    return calls


def test_draft_passes_the_configured_model(captured, settings):
    settings.APP_LLM_MODEL = "openai:gpt-5-mini"
    result = services.draft("a brief", instructions="be short")

    assert captured["model"] == "openai:gpt-5-mini"
    assert captured["skills"] == "be short"
    assert captured["brief"] == "a brief"
    assert result.revised == "r"


def test_draft_runs_without_instructions(captured):
    services.draft("a brief")
    assert captured["skills"] == ""
    assert captured["brief"] == "a brief"
