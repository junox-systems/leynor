from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.brands.models import Audience, Brand
from apps.orgs.models import OWNER, Membership, Organization, Role
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


class BrandViewTestCase(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.org = make_org(self.user)
        self.brand = Brand.objects.create(
            organization=self.org, name="Flying Eyes", industry="Music"
        )
        self.client.force_login(self.user)


class AccessTests(BrandViewTestCase):
    def test_the_list_requires_a_login(self):
        self.client.logout()
        response = self.client.get(reverse("brands"))
        assert response.status_code == 302
        assert reverse("account_login") in response["Location"]

    def test_a_user_without_an_organization_is_sent_to_create_one(self):
        homeless = make_user("hana")
        self.client.force_login(homeless)
        response = self.client.get(reverse("brand_new"))
        assert response.status_code == 302
        assert response["Location"] == reverse("orgs")


class ListTests(BrandViewTestCase):
    def test_the_list_shows_only_the_sessions_organization(self):
        outsider = make_user("otto")
        other = make_org(outsider, name="Other")
        Brand.objects.create(organization=other, name="Theirs")

        body = self.client.get(reverse("brands")).content.decode()
        assert "Flying Eyes" in body
        assert "Music" in body
        assert "Theirs" not in body

    def test_the_empty_state_explains_a_brand(self):
        Brand.objects.all().delete()
        body = self.client.get(reverse("brands")).content.decode()
        assert "No brands yet" in body
        assert "Projects can point at one" in body


class CreateTests(BrandViewTestCase):
    def test_a_brand_records_the_profile_fields(self):
        response = self.client.post(
            reverse("brand_new"),
            {
                "name": "Second Brand",
                "website": "https://second.example",
                "description": "Another client.",
                "industry": "Retail",
                "tone": "Plain",
            },
        )
        brand = Brand.objects.get(name="Second Brand")
        assert response.status_code == 302
        assert response["Location"] == reverse("brands")
        assert brand.organization == self.org
        assert brand.industry == "Retail"
        assert messages_of(response) == ["Second Brand added."]

    def test_a_duplicate_name_is_a_form_error_not_a_500(self):
        response = self.client.post(
            reverse("brand_new"),
            {
                "name": "Flying Eyes",
                "website": "",
                "description": "",
                "industry": "",
                "tone": "",
            },
        )
        assert response.status_code == 200
        assert Brand.objects.filter(name="Flying Eyes").count() == 1
        assert "already has a brand by that name" in response.content.decode()


class DetailTests(BrandViewTestCase):
    def test_the_detail_page_is_scoped_to_the_organization(self):
        outsider = make_user("otto")
        other = make_org(outsider, name="Other")
        theirs = Brand.objects.create(organization=other, name="Theirs")

        response = self.client.get(reverse("brand_detail", args=[theirs.pk]))
        assert response.status_code == 404

    def test_the_detail_page_lists_the_audiences(self):
        Audience.objects.create(
            brand=self.brand,
            name="Listeners who read credits",
            description="They play records front to back.",
            wants="A statement they can repeat.",
            barrier="Debuts are cut short.",
            primary=True,
        )
        body = self.client.get(reverse("brand_detail", args=[self.brand.pk])).content.decode()
        assert "Listeners who read credits" in body
        assert "They play records front to back." in body
        assert "Held back by Debuts are cut short." in body
        assert "Primary" in body

    def test_an_audience_is_added_from_the_brand_page(self):
        response = self.client.post(
            reverse("brand_detail", args=[self.brand.pk]),
            {
                "name": "Shoppers",
                "description": "They buy on price and read reviews.",
                "wants": "A reason to switch.",
                "barrier": "The last one disappointed them.",
                "primary": "on",
            },
        )
        audience = Audience.objects.get(brand=self.brand, name="Shoppers")
        assert response.status_code == 302
        assert response["Location"] == reverse("brand_detail", args=[self.brand.pk])
        assert audience.primary
        assert messages_of(response) == ["Shoppers added to Flying Eyes."]

    def test_a_second_primary_audience_is_a_form_error(self):
        Audience.objects.create(brand=self.brand, name="Regulars", primary=True)
        response = self.client.post(
            reverse("brand_detail", args=[self.brand.pk]),
            {"name": "Tourists", "description": "", "wants": "", "barrier": "", "primary": "on"},
        )
        assert response.status_code == 200
        assert "already has a primary audience" in response.content.decode()
        assert not Audience.objects.filter(name="Tourists").exists()

    def test_a_duplicate_audience_name_is_a_form_error(self):
        Audience.objects.create(brand=self.brand, name="Regulars")
        response = self.client.post(
            reverse("brand_detail", args=[self.brand.pk]),
            {"name": "Regulars", "description": "", "wants": "", "barrier": ""},
        )
        assert response.status_code == 200
        assert "already has an audience by that name" in response.content.decode()
