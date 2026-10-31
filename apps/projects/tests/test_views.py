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


class ProjectViewTestCase(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.org = make_org(self.user)
        self.project = Project.start(
            organization=self.org, title="Works", slug="works"
        )
        self.client.force_login(self.user)
        self.detail = reverse("project_detail", args=[self.project.pk])


class AccessTests(ProjectViewTestCase):
    def test_the_list_requires_a_login(self):
        self.client.logout()
        response = self.client.get(reverse("projects"))
        assert response.status_code == 302
        assert reverse("account_login") in response["Location"]

    def test_another_organizations_project_is_a_404(self):
        outsider = make_user("otto")
        other = make_org(outsider, name="Other")
        theirs = Project.start(organization=other, title="Theirs", slug="theirs")
        self.client.force_login(outsider)

        assert (
            self.client.get(reverse("project_detail", args=[theirs.pk])).status_code
            == 200
        )
        assert self.client.get(self.detail).status_code == 404

    def test_a_user_without_an_organization_is_sent_to_create_one(self):
        homeless = make_user("hana")
        self.client.force_login(homeless)
        response = self.client.get(reverse("project_new"))
        assert response.status_code == 302
        assert response["Location"] == reverse("orgs")


class ListTests(ProjectViewTestCase):
    def test_the_list_shows_only_the_sessions_organization(self):
        outsider = make_user("otto")
        other = make_org(outsider, name="Other")
        Project.start(organization=other, title="Theirs", slug="theirs")

        body = self.client.get(reverse("projects")).content.decode()
        assert "Works" in body
        assert "Theirs" not in body

    def test_the_empty_state_teaches_the_hierarchy(self):
        Project.objects.all().delete()
        body = self.client.get(reverse("projects")).content.decode()
        assert "No projects yet" in body
        assert "brief a campaign" in body


class CreateTests(ProjectViewTestCase):
    def test_the_slug_comes_from_the_title_when_left_empty(self):
        response = self.client.post(
            reverse("project_new"), {"title": "A Second Project", "slug": ""}
        )
        project = Project.objects.get(title="A Second Project")
        assert response.status_code == 302
        assert response["Location"] == reverse("project_detail", args=[project.pk])
        assert project.slug == "a-second-project"

    def test_a_duplicate_slug_is_a_form_error_not_a_500(self):
        response = self.client.post(
            reverse("project_new"), {"title": "Clash", "slug": "works"}
        )
        assert response.status_code == 200
        assert Project.objects.filter(slug="works").count() == 1
        assert "already uses that slug" in response.content.decode()


class DetailTests(ProjectViewTestCase):
    def test_the_project_lists_its_campaigns(self):
        Campaign.objects.create(
            project=self.project, title="Launch", slug="launch"
        )
        body = self.client.get(self.detail).content.decode()
        assert "Works" in body
        assert "Launch" in body

    def test_a_project_without_campaigns_teaches_the_next_step(self):
        body = self.client.get(self.detail).content.decode()
        assert "No campaigns yet" in body


class DeleteTests(ProjectViewTestCase):
    def test_deleting_a_project_takes_campaigns_and_reels_with_it(self):
        campaign = Campaign.objects.create(
            project=self.project, title="Launch", slug="launch"
        )
        reel = Reel.start(campaign=campaign, title="Flying Eyes", slug="flying-eyes")

        response = self.client.post(
            reverse("project_delete", args=[self.project.pk])
        )
        assert response.status_code == 302
        assert not Project.objects.filter(pk=self.project.pk).exists()
        assert not Campaign.objects.filter(pk=campaign.pk).exists()
        assert not Reel.objects.filter(pk=reel.pk).exists()
        assert messages_of(response) == ["Works deleted."]

    def test_delete_is_post_only(self):
        response = self.client.get(
            reverse("project_delete", args=[self.project.pk])
        )
        assert response.status_code == 405
