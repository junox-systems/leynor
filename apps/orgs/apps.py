from django.apps import AppConfig
from django.db.models.signals import post_migrate


class OrgsConfig(AppConfig):
    name = "apps.orgs"

    def ready(self):
        from . import signals  # noqa: F401
        from .rbac import seed_default_roles

        # Seeds the default roles (owner > admin > member) after every migrate.
        post_migrate.connect(seed_default_roles, sender=self)
