from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.brands.models import Audience, Brand
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
        self.brand = Brand.objects.create(organization=self.org, name="Flying Eyes")
        self.audience = Audience.objects.create(
            brand=self.brand,
            name="Regulars",
            description="They play records front to back.",
            primary=True,
        )
        self.project = Project.create(
            organization=self.org, title="Works", brand=self.brand
        )
        self.campaign = Campaign.objects.create(
            project=self.project, title="Launch"
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
        their_project = Project.create(organization=other, title="Theirs")
        theirs = Campaign.objects.create(project=their_project, title="Theirs")
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
            {
                "title": "Second Brief",
                "goal": "Book the spring tour without paid ads.",
                "audience": self.audience.pk,
            },
        )
        campaign = Campaign.objects.get(title="Second Brief")
        assert response.status_code == 302
        assert response["Location"] == reverse("campaign_detail", args=[campaign.pk])
        assert campaign.project == self.project
        assert "spring tour" in campaign.goal
        assert campaign.audience == self.audience
        assert messages_of(response) == ["Second Brief briefed."]

    def test_an_audience_from_another_brand_is_refused(self):
        other_brand = Brand.objects.create(organization=self.org, name="Other")
        theirs = Audience.objects.create(brand=other_brand, name="Tourists")
        response = self.client.post(
            self.new,
            {"title": "Misfire", "goal": "", "audience": theirs.pk},
        )
        assert response.status_code == 200
        assert not Campaign.objects.filter(title="Misfire").exists()
        assert "Select a valid choice" in response.content.decode()

    def test_a_campaign_without_a_brand_offers_no_audience(self):
        bare = Project.create(organization=self.org, title="Bare")
        response = self.client.get(reverse("campaign_new", args=[bare.pk]))
        assert response.status_code == 200
        assert "Set a brand on this project" in response.content.decode()

    def test_campaigns_may_share_a_title(self):
        response = self.client.post(
            self.new,
            {"title": "Launch", "goal": "", "audience": ""},
        )
        assert response.status_code == 302
        assert Campaign.objects.filter(title="Launch").count() == 2


class DetailTests(CampaignViewTestCase):
    def test_the_brief_lists_its_output_units(self):
        Reel.create(campaign=self.campaign, title="Flying Eyes", slug="flying-eyes")
        body = self.client.get(self.detail).content.decode()
        assert "Launch" in body
        assert "Flying Eyes" in body
        assert "On Spark" in body

    def test_a_campaign_without_units_teaches_the_reel_route(self):
        body = self.client.get(self.detail).content.decode()
        assert "No outputs yet" in body
        assert "Spark, Hook, Board, Look, Voice, Print" in body


class ListTests(CampaignViewTestCase):
    def test_the_list_shows_campaigns_with_their_project(self):
        other = Project.create(organization=self.org, title="Second")
        Campaign.objects.create(project=other, title="Second brief")

        body = self.client.get(reverse("campaigns")).content.decode()
        assert "Launch" in body
        assert "Second brief" in body
        assert "Works" in body

    def test_archived_projects_stay_out_of_the_list(self):
        self.project.status = Project.Status.ARCHIVED
        self.project.save()

        body = self.client.get(reverse("campaigns")).content.decode()
        assert "No campaigns yet" in body

    def test_the_empty_state_teaches_the_hierarchy(self):
        Campaign.objects.all().delete()
        body = self.client.get(reverse("campaigns")).content.decode()
        assert "No campaigns yet" in body
        assert "inside a project" in body
