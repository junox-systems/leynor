# apps/dashboard/panels.py
"""
Activity payload.

One function, one shape, consumed by ActivityView (rendered with `json_script`
into Svelte props) and the DMR refresh controller in apps/api. Single source of
truth for the panel — never serialize it twice.

The dashboard itself is server-rendered (templates/dashboard/index.html); only
the activity page keeps an island.
"""

from auditlog.models import LogEntry


def activity_payload(user, limit=10) -> dict:
    """Recent audited changes made by this user.

    Only models passed to `auditlog.register()` are recorded — today that is
    User, Project, Campaign and Reel, so older entries without an actor
    (cascade edits) stay out of it.
    """
    # LogEntry.Meta.ordering is ["-timestamp"], so no explicit order_by needed.
    entries = LogEntry.objects.filter(actor=user).select_related("content_type")[:limit]
    return {
        "entries": [
            {
                "id": entry.id,
                "action": entry.get_action_display(),
                "model": entry.content_type.name if entry.content_type else "",
                "object_repr": entry.object_repr,
                "timestamp": entry.timestamp.isoformat(),
                # Field NAMES only, never values — `changes` can carry password
                # hashes and other secrets straight out of the model.
                "fields": sorted(entry.changes or {}),
            }
            for entry in entries
        ]
    }
