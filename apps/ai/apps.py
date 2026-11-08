from django.apps import AppConfig


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai"
    label = "ai"
    verbose_name = "AI"

    def ready(self):
        from apps.ai import checks  # noqa: F401  (registers the system checks)
