"""Turn configured rows into pydantic-ai models, and talk to providers for the admin."""

from __future__ import annotations

import time

import httpx

from apps.ai.models import (
    OPENAI_COMPATIBLE,
    OPENCODE_GO,
    OPENCODE_GO_MODELS,
    OPENCODE_GO_URL,
    OWN_KINDS,
    Assignment,
    accepts,
    provider_class,
)
from apps.ai.registry import LLM, PURPOSES, default_for, label


class NoModel(RuntimeError):
    """No usable model for a job. The message tells a person what to set."""


def resolve(purpose: str) -> Assignment:
    """The job's own assignment, else its kind's default."""
    kind = PURPOSES[purpose][0]
    for key in dict.fromkeys((purpose, default_for(kind))):
        assignment = (
            Assignment.objects.select_related("model__provider", "fallback__provider")
            .filter(purpose=key)
            .first()
        )
        if assignment is not None:
            return assignment
    raise NoModel(
        f"No model for {label(purpose)}. Assign one under Admin → AI → Assignments, "
        f"or set {label(default_for(kind))}."
    )


def build(model, session: str | None = None):
    """A pydantic-ai model for one row. `session` names the conversation for
    providers that route on it. Raises NoModel with the reason."""
    if not model.usable:
        raise NoModel(f"{model} is disabled, or its provider is.")
    provider = model.provider
    headers = provider.request_headers(session)
    try:
        if provider.kind in OWN_KINDS:
            from openai import AsyncOpenAI
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            base_url = provider.base_url or (OPENCODE_GO_URL if provider.kind == OPENCODE_GO else "")
            # Headers on the client itself, so a custom User-Agent replaces the SDK's.
            client = AsyncOpenAI(
                base_url=base_url,
                api_key=provider.api_key or "not-needed",  # local servers take any key
                default_headers=headers or None,
            )
            return OpenAIChatModel(model.name, provider=OpenAIProvider(openai_client=client))
        from pydantic_ai.models import infer_model

        cls = provider_class(provider.kind)
        options = {}
        if provider.base_url and accepts(cls, "base_url"):
            options["base_url"] = provider.base_url
        if provider.api_key and accepts(cls, "api_key"):
            options["api_key"] = provider.api_key
        instance = cls(**options)
        if headers:
            instance = _with_headers(cls, instance, options, headers)
        return infer_model(f"{provider.kind}:{model.name}", provider_factory=lambda _: instance)
    except NoModel:
        raise
    except Exception as exc:  # missing key, bad URL, unknown model: say which provider
        raise NoModel(f"{provider.name} could not be used: {exc}") from exc


def _with_headers(cls, instance, options: dict, headers: dict):
    """The same provider, sending `headers` on every request."""
    # An SDK client copied with default_headers keeps the provider's own URL and
    # key, and lets a custom User-Agent replace the SDK's.
    for keyword in ("openai_client", "anthropic_client"):
        if accepts(cls, keyword):
            return cls(**{keyword: instance.client.with_options(default_headers=headers)})
    if accepts(cls, "http_client"):
        return cls(**options, http_client=httpx.AsyncClient(headers=headers, timeout=600))
    raise NoModel(f"{cls.__name__} cannot send extra headers.")


def llm(purpose: str, session: str | None = None):
    """(pydantic-ai model, model settings) for a language-model job.

    Pass one `session` per conversation (an idea, a reel) so providers that
    route or cache on it see every request of that conversation together.
    """
    assignment = resolve(purpose)
    if assignment.model.kind != LLM:
        raise NoModel(f"{assignment.model} is not a language model.")
    built = build(assignment.model, session)
    if assignment.fallback_id:
        from pydantic_ai.models.fallback import FallbackModel

        built = FallbackModel(built, build(assignment.fallback, session))
    return built, dict(assignment.model.settings)


def test(model) -> tuple[bool, str]:
    """Send one short prompt. (ok, what a person reads)."""
    from pydantic_ai import Agent

    started = time.monotonic()
    try:
        reply = Agent(build(model), model_settings=dict(model.settings)).run_sync(
            "Reply with the single word OK."
        )
    except Exception as exc:
        return False, f"{model}: {exc}"
    seconds = time.monotonic() - started
    return True, f"{model}: answered “{str(reply.output).strip()[:40]}” in {seconds:.1f} s."


# Where each provider lists its models, when no URL is set.
MODEL_LISTS = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "together": "https://api.together.xyz/v1",
    "fireworks": "https://api.fireworks.ai/inference/v1",
    "moonshotai": "https://api.moonshot.ai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
}


class CannotList(RuntimeError):
    pass


def remote_models(provider, client: httpx.Client | None = None) -> list[str]:
    """Model ids the provider offers, from its /models endpoint."""
    headers = provider.request_headers()
    if provider.kind == "anthropic":
        url = (provider.base_url or "https://api.anthropic.com").rstrip("/") + "/v1/models"
        headers |= {"x-api-key": provider.api_key, "anthropic-version": "2023-06-01"}
    elif provider.kind == OPENCODE_GO:
        url = OPENCODE_GO_MODELS
        headers |= {"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
    elif provider.kind == OPENAI_COMPATIBLE or provider.kind in MODEL_LISTS:
        base = provider.base_url or MODEL_LISTS[provider.kind]
        url = base.rstrip("/") + "/models"
        headers |= {"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
    else:
        raise CannotList(f"{provider.get_kind_display()} has no model list here; add models by hand.")
    client = client or httpx.Client(timeout=15)
    try:
        response = client.get(url, headers=headers, params={"limit": 1000})
        response.raise_for_status()
        rows = response.json().get("data", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise CannotList(f"{provider.name}: {exc}") from exc
    return sorted({str(row["id"]) for row in rows if row.get("id")})
