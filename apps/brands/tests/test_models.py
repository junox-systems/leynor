import pytest
from django.db import IntegrityError
from django.test import TestCase

from apps.brands.models import Audience, Brand
from apps.orgs.models import OWNER, Membership, Organization, Role
from apps.projects.models import Project
from apps.users.models import User


def make_org(user, name="Acme"):
    org = Organization.objects.create(name=name)
    membership = Membership.objects.create(organization=org, user=user)
    membership.roles.add(Role.objects.get(name=OWNER))
    return org


class BrandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@example.com", username="a", password="pw"
        )
        self.org = make_org(self.user)

    def test_names_are_unique_per_organization(self):
        Brand.objects.create(organization=self.org, name="Flying Eyes")
        with pytest.raises(IntegrityError):
            Brand.objects.create(organization=self.org, name="Flying Eyes")

    def test_the_same_name_is_free_in_another_organization(self):
        other = make_org(
            User.objects.create_user(
                email="b@example.com", username="b", password="pw"
            ),
            name="Other",
        )
        Brand.objects.create(organization=self.org, name="Flying Eyes")
        brand = Brand.objects.create(organization=other, name="Flying Eyes")
        assert brand.pk

    def test_a_brand_holds_more_than_a_name(self):
        brand = Brand.objects.create(
            organization=self.org,
            name="Flying Eyes",
            website="https://flyingeyes.example",
            description="A debut band.",
            industry="Music",
            tone="Warm, precise, never hyped",
        )
        assert brand.website.endswith("flyingeyes.example")
        assert brand.tone

    def test_several_projects_can_answer_one_brand(self):
        brand = Brand.objects.create(organization=self.org, name="Flying Eyes")
        first = Project.start(organization=self.org, title="Debut", brand=brand)
        second = Project.start(organization=self.org, title="Tour", brand=brand)
        assert set(brand.projects.all()) == {first, second}


class AudienceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@example.com", username="a", password="pw"
        )
        self.org = make_org(self.user)
        self.brand = Brand.objects.create(organization=self.org, name="Flying Eyes")

    def test_an_audience_records_who_it_is(self):
        audience = Audience.objects.create(
            brand=self.brand,
            name="Listeners who read credits",
            description="They play records front to back and want the liner notes.",
            wants="A statement they can repeat.",
            barrier="Debuts are cut short on radio.",
        )
        assert audience.brand == self.brand
        assert audience.wants

    def test_audience_names_are_unique_per_brand(self):
        Audience.objects.create(brand=self.brand, name="Regulars")
        with pytest.raises(IntegrityError):
            Audience.objects.create(brand=self.brand, name="Regulars")

    def test_the_same_name_is_free_on_another_brand(self):
        other = Brand.objects.create(organization=self.org, name="Second")
        Audience.objects.create(brand=self.brand, name="Regulars")
        audience = Audience.objects.create(brand=other, name="Regulars")
        assert audience.pk

    def test_a_brand_has_at_most_one_primary_audience(self):
        Audience.objects.create(brand=self.brand, name="Regulars", primary=True)
        with pytest.raises(IntegrityError):
            Audience.objects.create(brand=self.brand, name="Tourists", primary=True)

    def test_the_primary_audience_is_the_default_voice(self):
        Audience.objects.create(brand=self.brand, name="Regulars")
        primary = Audience.objects.create(brand=self.brand, name="Tourists", primary=True)
        assert self.brand.primary_audience == primary
