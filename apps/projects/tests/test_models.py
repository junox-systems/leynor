import pytest
from django.db import IntegrityError
from django.test import TestCase

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

    def test_start_creates_a_project_in_the_organization(self):
        project = Project.start(organization=self.org, title="Works", slug="works")
        assert project.organization == self.org
        assert project.campaigns.count() == 0

    def test_slugs_are_unique_per_organization(self):
        Project.start(organization=self.org, title="Works", slug="works")
        with pytest.raises(IntegrityError):
            Project.start(organization=self.org, title="Other", slug="works")

    def test_the_same_slug_is_free_in_another_organization(self):
        other = make_org(
            User.objects.create_user(
                email="b@example.com", username="b", password="pw"
            ),
            name="Other",
        )
        project = Project.start(organization=other, title="Works", slug="works")
        assert project.pk
