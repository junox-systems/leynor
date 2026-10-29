# apps/api/schemas/dashboard.py

import msgspec


class ActivityEntrySchema(msgspec.Struct):
    """One audited change in the dashboard activity feed."""

    id: int
    action: str
    model: str
    object_repr: str
    timestamp: str
    fields: list[str]
