from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.campaigns.models import Campaign
from apps.instagram.models import Reel
from apps.orgs.models import OWNER, Membership, Organization, Role
from apps.projects.models import Project
from apps.users.models import User

PASSWORD = "s3cret-pw"


def make_user(name):
    return User.objects.create_user(
        email=f"{name}@example.com", username=name, password=PASSWORD
    )


def make_org(user, name="Acme"):
    org = Organization.objects.create(name=name)
    membership = Membership.objects.create(organization=org, user=user)
    membership.roles.add(Role.objects.get(name=OWNER))
    return org


def messages_of(response):
    return [message.message for message in get_messages(response.wsgi_request)]


class CampaignViewTestCase(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.org = make_org(self.user)
        self.project = Project.start(
            organization=self.org, title="Works", slug="works"
        )
        self.campaign = Campaign.objects.create(
            project=self.project, title="Launch", slug="launch"
        )
        self.client.force_login(self.user)
        self.detail = reverse("campaign_detail", args=[self.campaign.pk])
        self.new = reverse("campaign_new", args=[self.project.pk])


class AccessTests(CampaignViewTestCase):
    def test_the_campaign_requires_a_login(self):
        self.client.logout()
        response = self.client.get(self.detail)
        assert response.status_code == 302
        assert reverse("account_login") in response["Location"]

    def test_another_organizations_campaign_is_a_404(self):
        outsider = make_user("otto")
        other = make_org(outsider, name="Other")
        their_project = Project.start(
            organization=other, title="Theirs", slug="theirs"
        )
        theirs = Campaign.objects.create(
            project=their_project, title="Theirs", slug="theirs"
        )
        self.client.force_login(outsider)

        assert (
            self.client.get(reverse("campaign_detail", args=[theirs.pk])).status_code
            == 200
        )
        assert self.client.get(self.detail).status_code == 404
        assert (
            self.client.get(
                reverse("campaign_new", args=[their_project.pk])
            ).status_code
            == 200
        )
        assert self.client.get(self.new).status_code == 404


class CreateTests(CampaignViewTestCase):
    def test_a_campaign_is_briefed_on_its_project(self):
        response = self.client.post(
            self.new,
            {"title": "Second Brief", "slug": "", "goal": "shares", "audience": "founders"},
        )
        campaign = Campaign.objects.get(title="Second Brief")
        assert response.status_code == 302
        assert response["Location"] == reverse("campaign_detail", args=[campaign.pk])
        assert campaign.project == self.project
        assert campaign.slug == "second-brief"
        assert messages_of(response) == ["Second Brief briefed."]

    def test_a_duplicate_slug_is_a_form_error_not_a_500(self):
        response = self.client.post(
            self.new,
            {"title": "Clash", "slug": "launch", "goal": "saves", "audience": ""},
        )
        assert response.status_code == 200
        assert Campaign.objects.filter(slug="launch").count() == 1
        assert "already uses that slug" in response.content.decode()


class DetailTests(CampaignViewTestCase):
    def test_the_brief_lists_its_output_units(self):
        Reel.start(campaign=self.campaign, title="Flying Eyes", slug="flying-eyes")
        body = self.client.get(self.detail).content.decode()
        assert "Launch" in body
        assert "Flying Eyes" in body
        assert "On Spark" in body

    def test_a_campaign_without_units_teaches_the_reel_route(self):
        body = self.client.get(self.detail).content.decode()
        assert "No outputs yet" in body
        assert "Spark, Hook, Board, Look, Voice, Print" in body
