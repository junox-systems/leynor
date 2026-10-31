import pytest
from django.db import IntegrityError
from django.test import TestCase

from apps.campaigns.models import Campaign
from apps.campaigns.registry import publisher, units
from apps.instagram.models import Reel
from apps.orgs.models import OWNER, Membership, Organization, Role
from apps.projects.models import Project
from apps.users.models import User


def make_org(user, name="Acme"):
    org = Organization.objects.create(name=name)
    membership = Membership.objects.create(organization=org, user=user)
    membership.roles.add(Role.objects.get(name=OWNER))
    return org


class CampaignTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@example.com", username="a", password="pw"
        )
        self.org = make_org(self.user)
        self.project = Project.start(
            organization=self.org, title="Works", slug="works"
        )
        self.campaign = Campaign.objects.create(
            project=self.project, title="Launch", slug="launch"
        )

    def test_slugs_are_unique_per_project(self):
        with pytest.raises(IntegrityError):
            Campaign.objects.create(
                project=self.project, title="Other", slug="launch"
            )

    def test_the_same_slug_is_free_in_another_project(self):
        other = Project.start(organization=self.org, title="Second", slug="second")
        assert (
            Campaign.objects.create(project=other, title="Launch", slug="launch").pk
        )

    def test_tenancy_resolves_through_the_project(self):
        assert self.campaign.organization == self.org

    def test_a_campaign_starts_with_no_output_units(self):
        assert units(self.campaign) == []

    def test_the_registry_finds_each_unit_with_its_url(self):
        from apps.linkedin.models import Post
        from apps.tiktok.models import TikTok
        from apps.twitter.models import Tweet

        reel = Reel.start(campaign=self.campaign, title="Flying Eyes", slug="flying-eyes")
        TikTok.objects.create(campaign=self.campaign, title="Cut", slug="cut")
        Tweet.objects.create(campaign=self.campaign, title="Thread", slug="thread")
        Post.objects.create(campaign=self.campaign, title="Essay", slug="essay")

        rows = {row["channel"]: row for row in units(self.campaign)}
        assert set(rows) == {"reel", "tiktok", "twitter", "linkedin"}
        assert rows["reel"]["url"] == f"/reels/{reel.pk}/"
        assert rows["tiktok"]["url"] == ""
        assert rows["reel"]["unit"].has_route is True
        assert rows["tiktok"]["unit"].has_route is False
        assert rows["tiktok"]["unit"].summary() == "Draft"

    def test_the_registry_builds_the_channel_publisher(self):
        from apps.instagram.publisher import InstagramPublisher

        assert isinstance(publisher("reel"), InstagramPublisher)

    def test_an_unbuilt_channel_refuses_to_publish(self):
        from apps.campaigns.adapters import PublishUnavailable

        with pytest.raises(PublishUnavailable):
            publisher("tiktok").publish(None)
