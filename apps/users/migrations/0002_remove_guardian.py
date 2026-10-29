"""Clean up after django-guardian, which the kit no longer uses.

Guardian's post_migrate hook created an "AnonymousUser" account (email login
means its email field held "anonymoususer", lowercased on save). Its tables
are dropped first, since they reference users.
"""

from django.db import migrations

GUARDIAN_TABLES = ["guardian_userobjectpermission", "guardian_groupobjectpermission"]


def remove_guardian(apps, schema_editor):
    existing = set(schema_editor.connection.introspection.table_names())
    for table in GUARDIAN_TABLES:
        if table in existing:
            schema_editor.execute(f"DROP TABLE {schema_editor.quote_name(table)}")
    schema_editor.execute("DELETE FROM django_migrations WHERE app = 'guardian'")
    # Cascades to guardian's auth Permission rows (and any grants of them).
    apps.get_model("contenttypes", "ContentType").objects.filter(
        app_label="guardian"
    ).delete()
    apps.get_model("users", "User").objects.filter(
        email__iexact="AnonymousUser"
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_squashed_0003_alter_user_id"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(remove_guardian, migrations.RunPython.noop)]
