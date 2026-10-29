import pytest
from django.urls import reverse
from allauth.account.models import EmailAddress

from apps.users.models import User

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

TOGGLE = "[data-controller=theme-toggle]"


def is_dark(page):
    return page.evaluate("document.documentElement.classList.contains('dark')")


@pytest.fixture
def errors(page):
    collected = []
    page.on("console", lambda m: m.type == "error" and collected.append(m.text))
    page.on("pageerror", lambda e: collected.append(str(e)))
    return collected


@pytest.fixture
def logged_in(page, client, live_server):
    user = User.objects.create_user(
        email="e2e@example.com", username="e2e", password="pw"
    )
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    client.force_login(user)
    page.context.add_cookies(
        [
            {
                "name": "sessionid",
                "value": client.cookies["sessionid"].value,
                "url": live_server.url,
            }
        ]
    )
    return page


def assert_toggles(page):
    page.evaluate("localStorage.clear()")
    page.reload()
    start = is_dark(page)
    page.click(TOGGLE)
    assert is_dark(page) is not start
    assert page.get_attribute(TOGGLE, "aria-pressed") == str(not start).lower()
    assert page.evaluate("localStorage.getItem('theme')") == (
        "light" if start else "dark"
    )
    return not start


def test_toggle_on_homepage(page, live_server, errors):
    page.goto(live_server.url + reverse("home"))
    assert_toggles(page)
    assert errors == []


def test_toggle_on_dashboard_survives_boosted_nav(logged_in, live_server, errors):
    page = logged_in
    page.goto(live_server.url + reverse("dashboard"))
    dark = assert_toggles(page)

    orgs = reverse("orgs")
    page.click(f"#app-sidebar a[href='{orgs}']")
    page.wait_for_url(f"**{orgs}")
    assert is_dark(page) is dark
    page.click(TOGGLE)
    assert is_dark(page) is not dark
    assert errors == []


def test_activity_page_mounts_from_sidebar(logged_in, live_server, errors):
    page = logged_in
    page.goto(live_server.url + reverse("dashboard"))
    page.click(f"#app-sidebar a[href='{reverse('activity')}']")
    page.wait_for_url(f"**{reverse('activity')}")
    page.get_by_role("heading", name="Recent activity").wait_for()
    page.get_by_role("heading", name="No activity yet").wait_for()
    page.get_by_role("button", name="Refresh").click()
    page.get_by_role("button", name="Refresh").wait_for()
    assert errors == []
