"""AI config: encrypted keys, building models from rows, resolving jobs, the admin."""

import httpx
import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.ai import services
from apps.ai.models import Assignment, Model, Provider
from apps.users.models import User

FERNET_KEY = "bGV5bm9yLWRlcGxveS1jaGVjay1vbmx5LWtleS0zMmI="


def provider(**fields):
    defaults = {"name": "OpenCode Go", "kind": "openai-compatible", "base_url": "https://opencode.ai/zen/go/v1", "api_key": "sk-go"}
    return Provider.objects.create(**{**defaults, **fields})


def model(on, name="kimi-k2.6", **fields):
    return Model.objects.create(provider=on, name=name, **fields)


@override_settings(APP_SECRETS_KEY=FERNET_KEY)
class SecretTests(TestCase):
    def test_the_key_is_encrypted_in_the_table_and_plain_in_python(self):
        row = provider(api_key="sk-secret-123")
        with connection.cursor() as cursor:
            pk = Provider._meta.pk.get_db_prep_value(row.pk, connection)
            cursor.execute("select api_key from ai_provider where id = %s", [pk])
            stored = cursor.fetchone()[0]
        assert "sk-secret-123" not in stored
        assert Provider.objects.get(pk=row.pk).api_key == "sk-secret-123"

    def test_a_key_from_another_secrets_key_reads_as_unset(self):
        row = provider(api_key="sk-secret-123")
        with override_settings(APP_SECRETS_KEY="b3RoZXItc2VjcmV0cy1rZXktZm9yLXRlc3RzLTMyYiE="):
            assert Provider.objects.get(pk=row.pk).api_key == ""

    def test_the_audit_log_never_records_the_key(self):
        row = provider(api_key="sk-secret-123")
        from auditlog.models import LogEntry

        changes = [entry.changes for entry in LogEntry.objects.get_for_object(row)]
        assert changes and all("api_key" not in str(change) for change in changes)


class ValidationTests(TestCase):
    def test_an_openai_compatible_provider_needs_its_url(self):
        with pytest.raises(ValidationError, match="needs its URL"):
            Provider(name="x", kind="openai-compatible").full_clean()

    def test_a_provider_that_takes_no_url_refuses_one(self):
        with pytest.raises(ValidationError, match="does not take a URL"):
            Provider(name="x", kind="openrouter", base_url="https://example.com").full_clean()

    def test_anthropic_takes_a_url_for_compatible_gateways(self):
        Provider(name="Go MiniMax", kind="anthropic", base_url="https://opencode.ai/zen/go").full_clean()

    def test_unknown_model_settings_are_refused(self):
        row = model(provider())
        row.settings = {"temperature": 0.3, "warmth": 9}
        with pytest.raises(ValidationError, match="warmth"):
            row.full_clean()

    def test_an_assignment_needs_the_jobs_kind_and_an_enabled_model(self):
        on = provider()
        image = model(on, name="flux", kind="image")
        with pytest.raises(ValidationError, match="needs a llm model"):
            Assignment(purpose="instagram.board", model=image).full_clean()
        off = model(on, name="old", enabled=False)
        with pytest.raises(ValidationError, match="disabled"):
            Assignment(purpose="instagram.board", model=off).full_clean()


class BuildTests(TestCase):
    def test_an_openai_compatible_row_builds_a_chat_model_on_its_url(self):
        built = services.build(model(provider()))
        assert type(built).__name__ == "OpenAIChatModel"
        assert built.model_name == "kimi-k2.6"
        assert str(built.client.base_url).startswith("https://opencode.ai/zen/go/v1")
        assert built.client.api_key == "sk-go"

    def test_a_native_provider_gets_its_key_and_url(self):
        claude = provider(name="Claude", kind="anthropic", base_url="", api_key="sk-ant")
        built = services.build(model(claude, name="claude-sonnet-5-5"))
        assert type(built).__name__ == "AnthropicModel"
        assert built.model_name == "claude-sonnet-5-5"

    def test_openrouter_takes_its_key(self):
        router = provider(name="OpenRouter", kind="openrouter", base_url="", api_key="sk-or")
        built = services.build(model(router, name="anthropic/claude-sonnet-5.5"))
        assert built.model_name == "anthropic/claude-sonnet-5.5"

    def test_claude_keeps_its_key_and_gets_the_headers(self):
        claude = provider(name="Claude", kind="anthropic", base_url="", api_key="sk-ant", session_header="x-session")
        built = services.build(model(claude, name="claude-sonnet-5-5"), session="reel-9")
        assert built.client.api_key == "sk-ant"
        assert built.client.default_headers["x-session"] == "reel-9"

    def test_a_disabled_model_is_refused_with_its_name(self):
        with pytest.raises(services.NoModel, match="disabled"):
            services.build(model(provider(), enabled=False))


class ResolveTests(TestCase):
    def setUp(self):
        on = provider()
        self.default = model(on, name="kimi-k2.6")
        self.board = model(on, name="glm-5")

    def test_without_any_assignment_the_error_says_where_to_set_one(self):
        with pytest.raises(services.NoModel, match=r"No model for Reel · Board\. Assign one under Admin → AI → Assignments, or set Default \(LLM\)"):
            services.llm("instagram.board")

    def test_a_job_without_its_own_assignment_uses_the_default(self):
        Assignment.objects.create(purpose="default.llm", model=self.default)
        built, _ = services.llm("instagram.board")
        assert built.model_name == "kimi-k2.6"

    def test_a_jobs_own_assignment_wins_and_carries_its_settings(self):
        Assignment.objects.create(purpose="default.llm", model=self.default)
        self.board.settings = {"temperature": 0.4}
        self.board.save()
        Assignment.objects.create(purpose="instagram.board", model=self.board)
        built, model_settings = services.llm("instagram.board")
        assert built.model_name == "glm-5"
        assert model_settings == {"temperature": 0.4}

    def test_a_fallback_wraps_both_models(self):
        Assignment.objects.create(purpose="instagram.hook", model=self.board, fallback=self.default)
        built, _ = services.llm("instagram.hook")
        assert type(built).__name__ == "FallbackModel"
        assert [m.model_name for m in built.models] == ["glm-5", "kimi-k2.6"]


class RemoteModelTests(TestCase):
    def mocked(self, handler):
        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_an_openai_style_list_is_read_with_the_bearer_key(self):
        seen = {}

        def handler(request):
            seen["url"], seen["auth"] = str(request.url), request.headers.get("authorization")
            return httpx.Response(200, json={"data": [{"id": "kimi-k2.6"}, {"id": "glm-5"}]})

        names = services.remote_models(provider(), client=self.mocked(handler))
        assert names == ["glm-5", "kimi-k2.6"]
        assert seen["url"].startswith("https://opencode.ai/zen/go/v1/models")
        assert seen["auth"] == "Bearer sk-go"

    def test_anthropic_lists_with_its_own_headers(self):
        def handler(request):
            assert request.headers["x-api-key"] == "sk-ant"
            return httpx.Response(200, json={"data": [{"id": "claude-sonnet-5-5"}]})

        claude = provider(name="Claude", kind="anthropic", base_url="", api_key="sk-ant")
        assert services.remote_models(claude, client=self.mocked(handler)) == ["claude-sonnet-5-5"]

    def test_a_refusal_becomes_a_readable_error(self):
        def handler(request):
            return httpx.Response(401, json={"error": "bad key"})

        with pytest.raises(services.CannotList, match="401"):
            services.remote_models(provider(), client=self.mocked(handler))


class AdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="root@example.com", username="root", password="pw-123456")
        self.client.force_login(self.admin)

    def test_saving_without_a_key_keeps_the_stored_one(self):
        row = provider(api_key="sk-keep")
        url = reverse("admin:ai_provider_change", args=[row.pk])
        page = self.client.get(url).content.decode()
        assert "sk-keep" not in page
        response = self.client.post(
            url,
            {
                "name": "OpenCode Go",
                "kind": "openai-compatible",
                "base_url": "https://opencode.ai/zen/go/v1",
                "api_key": "",
                "headers": "",
                "session_header": "",
                "enabled": "on",
                "models-TOTAL_FORMS": "0",
                "models-INITIAL_FORMS": "0",
            },
        )
        assert response.status_code == 302, response.content.decode()[:2000]
        assert Provider.objects.get(pk=row.pk).api_key == "sk-keep"

    def test_the_list_says_whether_a_key_is_set_never_what_it_is(self):
        provider(api_key="sk-hidden")
        page = self.client.get(reverse("admin:ai_provider_changelist")).content.decode()
        assert "sk-hidden" not in page
        assert ">set<" in page

    def test_assignments_list_what_each_unassigned_job_uses(self):
        on = provider()
        Assignment.objects.create(purpose="default.llm", model=model(on))
        page = self.client.get(reverse("admin:ai_assignment_changelist"), follow=True).content.decode()
        assert "Reel · Board has no model of its own; it uses OpenCode Go · kimi-k2.6." in page


class OpenCodeGoTests(TestCase):
    def go(self, **fields):
        return provider(**{"kind": "opencode-go", "base_url": "", **fields})

    def test_go_needs_only_a_key(self):
        Provider(name="Go", kind="opencode-go", api_key="sk-go").full_clean()

    def test_go_talks_to_its_own_endpoint_with_a_session_and_a_user_agent(self):
        built = services.build(model(self.go(), name="deepseek-v4.1-flash"), session="reel-42")
        assert str(built.client.base_url).startswith("https://opencode.ai/inference/go/openai/v1")
        sent = built.client.default_headers
        assert sent["x-opencode-session"] == "reel-42"
        assert sent["User-Agent"] == "leynor/1.0"

    def test_one_conversation_keeps_one_session_and_the_admin_test_gets_its_own(self):
        row = model(self.go(), name="glm-5.3")
        first = services.build(row, session="pitch-7").client.default_headers["x-opencode-session"]
        again = services.build(row, session="pitch-7").client.default_headers["x-opencode-session"]
        adhoc = services.build(row).client.default_headers["x-opencode-session"]
        assert first == again == "pitch-7"
        assert adhoc and adhoc != "pitch-7"

    def test_a_custom_user_agent_and_header_win(self):
        row = model(self.go(headers={"User-Agent": "reels/2.0", "X-Team": "north"}), name="kimi-k3")
        sent = services.build(row, session="s").client.default_headers
        assert sent["User-Agent"] == "reels/2.0"
        assert sent["X-Team"] == "north"

    def test_the_model_list_comes_from_gos_catalogue(self):
        seen = {}

        def handler(request):
            seen["url"], seen["ua"] = str(request.url), request.headers.get("user-agent")
            return httpx.Response(200, json={"data": [{"id": "kimi-k3"}, {"id": "glm-5.3"}]})

        names = services.remote_models(self.go(), client=httpx.Client(transport=httpx.MockTransport(handler)))
        assert names == ["glm-5.3", "kimi-k3"]
        assert seen["url"].startswith("https://opencode.ai/inference/go/v1/models")
        assert seen["ua"] == "leynor/1.0"


class HeaderTests(TestCase):
    def test_any_openai_compatible_provider_can_send_a_session_header(self):
        row = model(provider(session_header="x-conversation", headers={"X-Title": "Leynor"}))
        sent = services.build(row, session="reel-1").client.default_headers
        assert sent["x-conversation"] == "reel-1"
        assert sent["X-Title"] == "Leynor"

    def test_a_native_provider_carries_headers_on_its_http_client(self):
        router = provider(name="OpenRouter", kind="openrouter", base_url="", api_key="sk-or", headers={"X-Title": "Leynor"})
        built = services.build(model(router, name="anthropic/claude-sonnet-5.5"))
        assert built.model_name == "anthropic/claude-sonnet-5.5"
        assert built.client.default_headers["X-Title"] == "Leynor"
        assert "openrouter.ai" in str(built.client.base_url)
        assert built.client.default_headers["X-Title"] == "Leynor"
        assert "openrouter.ai" in str(built.client.base_url)

    def test_claude_keeps_its_key_and_gets_the_headers(self):
        claude = provider(name="Claude", kind="anthropic", base_url="", api_key="sk-ant", session_header="x-session")
        built = services.build(model(claude, name="claude-sonnet-5-5"), session="reel-9")
        assert built.client.api_key == "sk-ant"
        assert built.client.default_headers["x-session"] == "reel-9"

    def test_a_provider_without_an_http_client_refuses_headers(self):
        with pytest.raises(ValidationError, match="does not take extra headers"):
            Provider(name="AWS", kind="bedrock", headers={"X": "1"}).full_clean()

    def test_headers_must_be_an_object(self):
        with pytest.raises(ValidationError, match="JSON object"):
            Provider(name="x", kind="openai", headers=["nope"]).full_clean()


class MigrationTests(TestCase):
    def test_a_hand_made_opencode_provider_becomes_opencode_go_and_keeps_its_data(self):
        import importlib

        from django.apps import apps

        convert = importlib.import_module("apps.ai.migrations.0002_opencode_go_and_headers").to_opencode_go
        go = provider(base_url="https://opencode.ai/inference/openai/v1", api_key="sk-keep")
        other = provider(name="LM Studio", base_url="http://host.docker.internal:1234/v1")
        flash = model(go, name="deepseek-v4.1-flash")
        Assignment.objects.create(purpose="default.llm", model=flash)

        convert(apps, None)

        go.refresh_from_db()
        other.refresh_from_db()
        assert (go.kind, go.base_url, go.api_key) == ("opencode-go", "", "sk-keep")
        assert other.kind == "openai-compatible"
        assert services.resolve("instagram.board").model == flash
