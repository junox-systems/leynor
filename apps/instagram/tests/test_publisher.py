"""The publisher's shape, with the transport faked. No network."""

import pytest
from django.test import TestCase, override_settings

from apps.campaigns.adapters import PublishUnavailable
from apps.campaigns.models import Campaign
from apps.instagram.models import InstagramPublication, Reel
from apps.instagram.publisher import InstagramPublisher
from apps.projects.models import Project
from apps.users.models import User


class PublisherTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@example.com", username="a", password="pw"
        )
        project = Project.create(organization=self._organization(), title="Works")
        self.campaign = Campaign.objects.create(project=project, title="Launch")
        self.reel = Reel.create(
            campaign=self.campaign, title="Flying Eyes", slug="flying-eyes"
        )

    def _organization(self):
        from apps.orgs.models import OWNER, Membership, Organization, Role

        org = Organization.objects.create(name="Acme")
        membership = Membership.objects.create(organization=org, user=self.user)
        membership.roles.add(Role.objects.get(name=OWNER))
        return org

    @override_settings(INSTAGRAM_ACCOUNT_ID="", INSTAGRAM_ACCESS_TOKEN="")
    def test_it_refuses_without_credentials(self):
        with pytest.raises(PublishUnavailable):
            InstagramPublisher().publish(self.reel, video_url="https://cdn/x.mp4")

    @override_settings(
        INSTAGRAM_ACCOUNT_ID="acct",
        INSTAGRAM_ACCESS_TOKEN="token",
        PUBLIC_MEDIA_BASE_URL="",
    )
    def test_it_refuses_without_a_public_media_base(self):
        with pytest.raises(PublishUnavailable):
            InstagramPublisher().publish(self.reel)

    def test_it_publishes_through_the_transport(self):
        calls = []

        def transport(method, url, params):
            calls.append((method, url, params))
            if url.endswith("media_publish"):
                return {"id": "published-1"}
            return {"id": "container-1"}

        publisher = InstagramPublisher(
            account_id="acct", token="token", transport=transport
        )
        external = publisher.publish(self.reel, video_url="https://cdn/x.mp4")

        assert external == "published-1"
        assert calls[0][2]["media_type"] == "REELS"
        assert calls[0][2]["video_url"] == "https://cdn/x.mp4"
        assert calls[1][2]["creation_id"] == "container-1"
        publication = InstagramPublication.objects.get(reel=self.reel)
        assert publication.external_id == "published-1"
        assert publication.published_at is not None

    @override_settings(INSTAGRAM_ACCOUNT_ID="acct", INSTAGRAM_ACCESS_TOKEN="token")
    def test_stats_writes_the_publication_row(self):
        InstagramPublication.objects.create(reel=self.reel, external_id="media-9")

        def transport(method, url, params):
            assert method == "GET"
            return {"like_count": 4, "comments_count": 1}

        publisher = InstagramPublisher(transport=transport)
        assert publisher.stats(self.reel) == {"like_count": 4, "comments_count": 1}
        publisher.refresh(self.reel)
        publication = InstagramPublication.objects.get(reel=self.reel)
        assert publication.stats["like_count"] == 4

    @override_settings(INSTAGRAM_ACCOUNT_ID="acct", INSTAGRAM_ACCESS_TOKEN="token")
    def test_stats_without_a_publication_is_empty(self):
        assert InstagramPublisher(transport=lambda *a: {}).stats(self.reel) == {}
