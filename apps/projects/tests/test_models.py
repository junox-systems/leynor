from django.test import TestCase

from apps.brands.models import Brand
from apps.orgs.models import OWNER, Membership, Organization, Role
from apps.projects.models import Project
from apps.users.models import User


def make_org(user, name="Acme"):
    org = Organization.objects.create(name=name)
    membership = Membership.objects.create(organization=org, user=user)
    membership.roles.add(Role.objects.get(name=OWNER))
    return org


class ProjectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@example.com", username="a", password="pw"
        )
        self.org = make_org(self.user)

    def test_start_creates_an_active_workspace_in_the_organization(self):
        project = Project.start(organization=self.org, title="Works")
        assert project.organization == self.org
        assert project.status == Project.Status.ACTIVE
        assert project.archived is False
        assert project.brand is None
        assert project.description == ""
        assert project.campaigns.count() == 0

    def test_start_takes_an_optional_brand_and_a_description(self):
        brand = Brand.objects.create(organization=self.org, name="Flying Eyes")
        project = Project.start(
            organization=self.org,
            title="Works",
            brand=brand,
            description="Debut album campaign.",
        )
        assert project.brand == brand
        assert project.description == "Debut album campaign."
        assert list(brand.projects.all()) == [project]

    def test_two_projects_may_share_a_title(self):
        Project.start(organization=self.org, title="Works")
        second = Project.start(organization=self.org, title="Works")
        assert second.pk

    def test_archived_projects_stay_readable(self):
        project = Project.start(organization=self.org, title="Old work")
        project.status = Project.Status.ARCHIVED
        project.save()
        assert project.archived is True
