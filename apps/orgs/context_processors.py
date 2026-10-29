# apps/orgs/context_processors.py
"""Organization switcher data for the dashboard (dashboard/index.html)."""

from django.utils.functional import SimpleLazyObject

from . import rbac


def current_org(request):
    """`org_switcher.current` (session's organization) and `.organizations` (all of the user's).

    Lazy: pages that never render the switcher run no queries.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    def load():
        session = rbac.current_session(request)
        return {
            "current": session.organization if session else None,
            "organizations": [
                m.organization
                for m in user.memberships.select_related("organization").order_by(
                    "organization__name"
                )
            ],
        }

    return {"org_switcher": SimpleLazyObject(load)}
