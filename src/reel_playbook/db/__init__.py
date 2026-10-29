"""Django ORM bootstrap. One app, one schema, no web layer."""

import os

DEFAULT_DB = "postgresql://postgres:postgres@127.0.0.1:5432/reel"


def setup(url: str | None = None) -> None:
    import django
    from django.apps import apps

    if url:
        current = os.environ.get("REEL_DB")
        if current and current != url and apps.ready:
            raise RuntimeError(
                f"django is already configured for {current}; one database per process"
            )
        os.environ["REEL_DB"] = url
    os.environ.setdefault("REEL_DB", DEFAULT_DB)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reel_playbook.db.settings")
    if not apps.ready:
        django.setup()


def migrate() -> None:
    from django.core.management import call_command

    setup()
    call_command("migrate", verbosity=0, interactive=False)
