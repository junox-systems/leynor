"""Drafting wiring: settings pick the model, the graph does the work."""

import pytest

from apps.creative import services
from apps.creative.graphs import DraftDeps
from apps.creative.results import DraftResult
from apps.projects.gates import Step


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

    def fake_run_draft(step, brief, deps):
        calls["step"] = step
        calls["brief"] = brief
        calls["deps"] = deps
        return DraftResult(step=step, draft="d", critique="c", revised="r", revisions=1)

    monkeypatch.setattr(services, "build_agents", fake_build_agents)
    monkeypatch.setattr(services, "run_draft", fake_run_draft)
    return calls


def test_draft_passes_the_configured_model(captured, settings):
    settings.APP_LLM_MODEL = "openai:gpt-5-mini"
    result = services.draft(Step.IDEA)

    assert captured["model"] == "openai:gpt-5-mini"
    assert captured["step"] is Step.IDEA
    assert captured["brief"] == services.resolve(Step.IDEA).prompt
    assert result.revised == "r"


def test_draft_uses_the_brief_it_is_given(captured):
    services.draft(Step.HOOK, "explicit brief")
    assert captured["brief"] == "explicit brief"


def test_draft_rejects_a_non_drafting_step(captured):
    with pytest.raises(services.NotADraftingStep):
        services.draft(Step.VOICE)
