"""Providers, the models they serve, and which model does which job.

Operator-managed in the admin and global to the install. Engines never read
these rows: a channel asks `apps.ai.services` for a built model and hands it on.
"""

import inspect
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from pydantic_ai.settings import ModelSettings

from apps.ai.fields import EncryptedTextField
from apps.ai.registry import KINDS, LLM, PURPOSES
from apps.core.models import BaseModel

OPENAI_COMPATIBLE = "openai-compatible"
OPENCODE_GO = "opencode-go"

# Built here rather than by pydantic-ai: both speak OpenAI chat completions.
OWN_KINDS = (OPENAI_COMPATIBLE, OPENCODE_GO)

# OpenCode Go: one chat-completions endpoint serves every text model (the
# console translates); the model list lives one level up.
# https://opencode.ai/docs/console/go#endpoints
OPENCODE_GO_URL = "https://opencode.ai/inference/go/openai/v1"
OPENCODE_GO_MODELS = "https://opencode.ai/inference/go/v1/models"
OPENCODE_GO_SESSION = "x-opencode-session"

# pydantic-ai providers installed here. groq, mistral and xai need SDK extras;
# all three also serve an OpenAI-compatible API, so use that kind for them.
PROVIDER_KINDS = [
    (OPENCODE_GO, "OpenCode Go"),
    (OPENAI_COMPATIBLE, "OpenAI-compatible URL (LM Studio, LiteLLM, Groq…)"),
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic (Claude)"),
    ("openrouter", "OpenRouter"),
    ("google", "Google (Gemini)"),
    ("ollama", "Ollama"),
    ("vllm", "vLLM"),
    ("deepseek", "DeepSeek"),
    ("together", "Together"),
    ("fireworks", "Fireworks"),
    ("cerebras", "Cerebras"),
    ("moonshotai", "Moonshot AI"),
    ("azure", "Azure OpenAI"),
    ("bedrock", "AWS Bedrock"),
    ("litellm", "LiteLLM"),
]

SETTING_KEYS = frozenset(ModelSettings.__annotations__)


def provider_class(kind: str):
    """The pydantic-ai provider class for a kind; raises ValidationError if unusable."""
    from pydantic_ai.providers import infer_provider_class

    try:
        return infer_provider_class(kind)
    except ImportError as exc:
        raise ValidationError(f"{kind} needs an extra package: {exc}") from None
    except ValueError:
        raise ValidationError(f"pydantic-ai has no provider called {kind}.") from None


def accepts(cls, keyword: str) -> bool:
    return keyword in inspect.signature(cls.__init__).parameters


class Provider(BaseModel):
    name = models.CharField(max_length=80, unique=True, help_text="What people call it, e.g. OpenCode Go.")
    kind = models.CharField(max_length=24, choices=PROVIDER_KINDS)
    base_url = models.URLField(
        blank=True,
        help_text="Blank uses the provider's own address. Needed for an OpenAI-compatible URL, "
        "e.g. http://host.docker.internal:11434/v1.",
    )
    api_key = EncryptedTextField(
        blank=True,
        help_text="Stored encrypted. Blank uses the provider's own environment variable, if any.",
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text='Extra HTTP headers on every request, e.g. {"User-Agent": "leynor/1.0"}. '
        "Not for API keys: headers are stored in plain text.",
    )
    session_header = models.CharField(
        max_length=80,
        blank=True,
        help_text="A header filled with one stable id per conversation (one per idea, one per reel), "
        f"e.g. {OPENCODE_GO_SESSION}. OpenCode Go uses that one when this is blank.",
    )
    enabled = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        ordering = ["name"]

    def __str__(self):
        return self.name

    def request_headers(self, session: str | None = None) -> dict[str, str]:
        """Static headers plus the session header, with OpenCode Go's defaults."""
        headers = {str(k): str(v) for k, v in (self.headers or {}).items()}
        session_header = self.session_header
        if self.kind == OPENCODE_GO:
            session_header = session_header or OPENCODE_GO_SESSION
            # Go asks every client to name itself, not the SDK.
            if not any(k.lower() == "user-agent" for k in headers):
                headers["User-Agent"] = f"{settings.APP_SLUG}/1.0"
        if session_header:
            headers[session_header] = session or uuid.uuid4().hex
        return headers

    def clean(self):
        if not isinstance(self.headers, dict) or not all(
            isinstance(v, (str, int, float)) for v in self.headers.values()
        ):
            raise ValidationError({"headers": 'Headers are a JSON object of names to values, e.g. {"User-Agent": "leynor/1.0"}.'})
        if self.kind == OPENCODE_GO:
            return
        if self.kind == OPENAI_COMPATIBLE:
            if not self.base_url:
                raise ValidationError({"base_url": "An OpenAI-compatible provider needs its URL."})
            return
        cls = provider_class(self.kind)
        if (self.headers or self.session_header) and not accepts(cls, "http_client"):
            raise ValidationError({"headers": f"{self.get_kind_display()} does not take extra headers."})
        if self.base_url and not accepts(cls, "base_url"):
            raise ValidationError(
                {
                    "base_url": f"{self.get_kind_display()} does not take a URL. For another "
                    "endpoint, choose OpenAI-compatible."
                }
            )


class Model(BaseModel):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="models")
    kind = models.CharField(max_length=12, choices=KINDS, default=LLM)
    name = models.CharField(
        max_length=200,
        help_text="The provider's model id, e.g. kimi-k2.6, claude-sonnet-5-5, anthropic/claude-sonnet-5.5.",
    )
    label = models.CharField(max_length=120, blank=True, help_text="Optional display name.")
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text='pydantic-ai model settings, e.g. {"temperature": 0.7, "max_tokens": 4000}.',
    )
    enabled = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        ordering = ["provider__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "name"], name="one_model_name_per_provider")
        ]

    def __str__(self):
        return self.label or f"{self.provider.name} · {self.name}"

    @property
    def usable(self) -> bool:
        return self.enabled and self.provider.enabled

    def clean(self):
        if not isinstance(self.settings, dict):
            raise ValidationError({"settings": "Settings are a JSON object."})
        unknown = set(self.settings) - SETTING_KEYS
        if unknown:
            raise ValidationError(
                {"settings": f"Unknown settings: {', '.join(sorted(unknown))}. Known: {', '.join(sorted(SETTING_KEYS))}."}
            )


class Assignment(BaseModel):
    """The model one job uses. A job without one uses its kind's default."""

    purpose = models.CharField(
        max_length=64,
        unique=True,
        choices=[(key, label) for key, (_, label) in PURPOSES.items()],
    )
    model = models.ForeignKey(Model, on_delete=models.PROTECT, related_name="assignments")
    fallback = models.ForeignKey(
        Model,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fallback_for",
        help_text="Tried when the first model errors, e.g. on a rate limit.",
    )

    class Meta(BaseModel.Meta):
        ordering = ["purpose"]

    def __str__(self):
        return self.get_purpose_display()

    def clean(self):
        kind = PURPOSES.get(self.purpose, (None,))[0]
        for field in ("model", "fallback"):
            chosen = getattr(self, field, None) if getattr(self, f"{field}_id") else None
            if chosen is None:
                continue
            if chosen.kind != kind:
                raise ValidationError({field: f"This job needs a {kind} model; {chosen} is {chosen.kind}."})
            if not chosen.usable:
                raise ValidationError({field: f"{chosen} or its provider is disabled."})
        if self.fallback_id and self.fallback_id == self.model_id:
            raise ValidationError({"fallback": "The fallback must be a different model."})
