from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.core.tasks import send_test_email
from apps.orgs.models import Invitation, Organization
from apps.orgs.tasks import send_invitation_email


def html_part(message):
    return next(body for body, mime in message.alternatives if mime == "text/html")


class HtmlEmailTests(TestCase):
    def test_allauth_mail_gets_html_part_with_clickable_link(self):
        self.client.post(
            reverse("account_signup"),
            {
                "email": "html@example.com",
                "username": "html",
                "password1": "a-long-s3cret-pw",
                "password2": "a-long-s3cret-pw",
            },
        )
        confirm = next(m for m in mail.outbox if "/accounts/confirm-email/" in m.body)
        self.assertIn(
            '<a href="http://testserver/accounts/confirm-email/', html_part(confirm)
        )

    def test_task_mail_carries_html_part(self):
        send_test_email("Hi <there>", "Body", ["a@example.com"])
        html = html_part(mail.outbox[-1])
        self.assertIn("Hi &lt;there&gt;", html)  # escaped, not injected

    def test_invitation_mail_links_accept_url(self):
        org = Organization.objects.create(name="Acme")
        invitation = Invitation.objects.create(organization=org, email="i@example.com")
        send_invitation_email(invitation.id, "http://testserver/accept/x/")
        self.assertIn(
            '<a href="http://testserver/accept/x/"', html_part(mail.outbox[-1])
        )
