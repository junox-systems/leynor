from auditlog.registry import auditlog
from django import forms
from django.contrib import admin, messages
from django.db import models
from django.db.models import Count

from apps.ai import services
from apps.ai.models import Assignment, Model, Provider
from apps.ai.registry import PURPOSES


def _formfield(field, **kwargs):
    if isinstance(field, models.URLField):
        kwargs["assume_scheme"] = "https"
    return field.formfield(**kwargs)


class ProviderForm(forms.ModelForm):
    api_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Stored encrypted and never shown again. Leave blank to keep the current key.",
    )
    clear_api_key = forms.BooleanField(required=False, label="Remove the stored key")

    class Meta:
        model = Provider
        fields = ["name", "kind", "base_url", "api_key", "headers", "session_header", "enabled"]
        formfield_callback = _formfield

    def clean_headers(self):
        return self.cleaned_data.get("headers") or {}

    def clean_api_key(self):
        entered = self.cleaned_data.get("api_key", "").strip()
        if self.data.get("clear_api_key"):
            return ""
        return entered or (self.instance.api_key if self.instance.pk else "")


class ModelInline(admin.TabularInline):
    model = Model
    extra = 0
    fields = ("name", "kind", "label", "enabled")
    show_change_link = True


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    form = ProviderForm
    formfield_overrides = {models.URLField: {"assume_scheme": "https"}}
    list_display = ("name", "kind", "base_url", "key", "enabled", "model_count")
    list_filter = ("kind", "enabled")
    search_fields = ("name",)
    inlines = [ModelInline]
    actions = ["import_models"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(model_count=Count("models"))

    @admin.display(description="API key")
    def key(self, provider):
        return "set" if provider.api_key else "not set"

    @admin.display(description="Models", ordering="model_count")
    def model_count(self, provider):
        return provider.model_count

    def changelist_view(self, request, extra_context=None):
        if not Provider.objects.exists():
            messages.info(
                request,
                "No providers yet. 1) Add one, e.g. OpenCode Go with just its key. "
                "2) Import or add its models. "
                "3) Under Assignments, set Default (LLM) and, if you like, one model per step.",
            )
        return super().changelist_view(request, extra_context)

    @admin.action(description="Import models from the provider")
    def import_models(self, request, queryset):
        for provider in queryset:
            try:
                names = services.remote_models(provider)
            except services.CannotList as exc:
                self.message_user(request, str(exc), messages.WARNING)
                continue
            known = set(provider.models.values_list("name", flat=True))
            new = [Model(provider=provider, name=name, enabled=False) for name in names if name not in known]
            Model.objects.bulk_create(new)
            self.message_user(
                request,
                f"{provider}: {len(new)} new model(s), {len(names) - len(new)} already here. "
                "New ones start disabled; enable the ones you use.",
            )


@admin.register(Model)
class ModelAdmin(admin.ModelAdmin):
    list_display = ("__str__", "provider", "name", "kind", "enabled", "jobs")
    list_filter = ("kind", "enabled", "provider")
    list_editable = ("enabled",)
    search_fields = ("name", "label", "provider__name")
    list_select_related = ("provider",)
    actions = ["test_models", "enable", "disable"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("assignments")

    @admin.display(description="Assigned to")
    def jobs(self, model):
        return ", ".join(a.get_purpose_display() for a in model.assignments.all()) or "—"

    @admin.action(description="Test: send one short prompt")
    def test_models(self, request, queryset):
        for model in queryset.select_related("provider"):
            ok, text = services.test(model)
            self.message_user(request, text, messages.SUCCESS if ok else messages.ERROR)

    @admin.action(description="Enable")
    def enable(self, request, queryset):
        queryset.update(enabled=True)

    @admin.action(description="Disable")
    def disable(self, request, queryset):
        queryset.update(enabled=False)


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["purpose", "model", "fallback"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usable = Model.objects.filter(enabled=True, provider__enabled=True).select_related("provider")
        self.fields["model"].queryset = usable
        self.fields["fallback"].queryset = usable


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    form = AssignmentForm
    list_display = ("__str__", "purpose", "model", "fallback")
    list_select_related = ("model__provider", "fallback__provider")

    def changelist_view(self, request, extra_context=None):
        assigned = set(Assignment.objects.values_list("purpose", flat=True))
        for purpose, (kind, label) in PURPOSES.items():
            if purpose in assigned:
                continue
            try:
                used = services.resolve(purpose).model
                messages.info(request, f"{label} has no model of its own; it uses {used}.")
            except services.NoModel as exc:
                messages.warning(request, str(exc))
        return super().changelist_view(request, extra_context)


auditlog.register(Provider, exclude_fields=["api_key"])
auditlog.register(Model)
auditlog.register(Assignment)
