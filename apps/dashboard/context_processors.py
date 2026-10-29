# apps/dashboard/context_processors.py
"""App shell navigation.

The sidebar is a persistent Svelte island (Sidebar.svelte) that survives htmx
navigations, so it cannot re-render from server HTML per page. It therefore
receives its links once as props and tracks the active item client-side.

URLs are resolved here rather than hardcoded in JS. Icon names are keys into a
map inside Sidebar.svelte — never pass raw SVG markup through JSON.
"""

from functools import lru_cache

from django.conf import settings
from django.urls import reverse


def _item(label, urlname, icon, **extra):
    return {"label": label, "href": reverse(urlname), "icon": icon, **extra}


@lru_cache(maxsize=2)
def _groups(is_staff):
    """Cached: these URLs are static, and this runs on every request."""
    account = [
        _item("Activity", "activity", "activity"),
        _item("Profile", "profile", "user"),
        _item("Organizations", "orgs", "users"),
        _item("Email addresses", "account_email", "mail"),
        _item("Password", "account_change_password", "key"),
        _item("Two-factor", "mfa_index", "smartphone"),
        _item("Connections", "socialaccount_connections", "link"),
    ]
    if is_staff:
        # Admin is outside the boosted shell — force a full page load.
        account.append(_item("Admin", "admin:index", "shield", boost=False))

    return [
        {
            "label": "Application",
            "items": [_item("Dashboard", "dashboard", "dashboard")],
        },
        {"label": "Account", "items": account},
    ]


def app_nav(request):
    """Sidebar groups for base_app.html. Anonymous pages get nothing."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "app_nav": {
            "name": settings.APP_NAME,
            "groups": _groups(user.is_staff),
        }
    }
