from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.campaigns.models import Campaign
from apps.instagram.gates import GateResult, Step
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


def make_campaign(org, title="Launch"):
    project = Project.start(organization=org, title=f"Works {title}")
    return Campaign.objects.create(project=project, title=title)


def messages_of(response):
    return [message.message for message in get_messages(response.wsgi_request)]


class ReelViewTestCase(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.org = make_org(self.user)
        self.campaign = make_campaign(self.org)
        self.reel = Reel.start(
            campaign=self.campaign, title="Flying Eyes", slug="flying-eyes"
        )
        self.client.force_login(self.user)
        self.detail = reverse("reel_detail", args=[self.reel.pk])

    def gate_url(self, step):
        return reverse("gate_decide", args=[self.reel.pk, step])


class AccessTests(ReelViewTestCase):
    def test_the_reel_requires_a_login(self):
        self.client.logout()
        response = self.client.get(self.detail)
        assert response.status_code == 302
        assert reverse("account_login") in response["Location"]

    def test_another_organizations_reel_is_a_404(self):
        outsider = make_user("otto")
        other = make_org(outsider, name="Other")
        theirs_campaign = make_campaign(other, title="Theirs")
        theirs = Reel.start(campaign=theirs_campaign, title="Theirs", slug="theirs")
        self.client.force_login(outsider)

        assert (
            self.client.get(reverse("reel_detail", args=[theirs.pk])).status_code == 200
        )
        assert self.client.get(self.detail).status_code == 404


class CreateTests(ReelViewTestCase):
    def test_the_slug_comes_from_the_title_when_left_empty(self):
        response = self.client.post(
            reverse("reel_new", args=[self.campaign.pk]),
            {"title": "A Second Reel", "slug": "", "target_seconds": 90},
        )
        reel = Reel.objects.get(title="A Second Reel")
        assert response.status_code == 302
        assert response["Location"] == reverse("reel_detail", args=[reel.pk])
        assert reel.slug == "a-second-reel"
        assert reel.gates.count() == 6

    def test_a_duplicate_slug_is_a_form_error_not_a_500(self):
        response = self.client.post(
            reverse("reel_new", args=[self.campaign.pk]),
            {"title": "Clash", "slug": "flying-eyes", "target_seconds": 60},
        )
        assert response.status_code == 200
        assert Reel.objects.filter(slug="flying-eyes").count() == 1
        assert "already uses that slug" in response.content.decode()

    def test_a_reel_outside_the_duration_window_is_refused(self):
        response = self.client.post(
            reverse("reel_new", args=[self.campaign.pk]),
            {"title": "Short", "slug": "short", "target_seconds": 30},
        )
        assert response.status_code == 200
        assert not Reel.objects.filter(slug="short").exists()


class GateTests(ReelViewTestCase):
    def test_approving_the_current_gate_advances_the_route(self):
        response = self.client.post(
            self.gate_url(Step.IDEA),
            {"action": "approve", "note": "cited input"},
            follow=True,
        )
        gate = self.reel.gates.get(step=Step.IDEA)
        assert gate.result == GateResult.AUTO
        assert gate.decided_by == self.user
        assert gate.note == "cited input"
        assert self.reel.current_gate.step == Step.HOOK.value
        assert messages_of(response) == ["Spark passed."]

    def test_a_human_gate_is_recorded_as_approved_not_auto(self):
        board = self.reel.gates.get(step=Step.BOARD)
        for step in (Step.IDEA, Step.HOOK):
            self.reel.gates.get(step=step).decide(GateResult.AUTO, self.user)
        self.client.post(self.gate_url(Step.BOARD), {"action": "approve"})
        assert board.__class__.objects.get(pk=board.pk).result == GateResult.APPROVED

    def test_a_gate_ahead_of_the_route_is_refused_with_a_message(self):
        response = self.client.post(
            self.gate_url(Step.HOOK), {"action": "approve"}, follow=True
        )
        assert self.reel.gates.get(step=Step.HOOK).result == GateResult.PENDING
        assert "not the step in play" in messages_of(response)[0]

    def test_an_auto_gate_cannot_be_sent_back(self):
        response = self.client.post(
            self.gate_url(Step.IDEA), {"action": "reject"}, follow=True
        )
        assert self.reel.gates.get(step=Step.IDEA).result == GateResult.PENDING
        assert "only a person can send a step back" in messages_of(response)[0]

    def test_a_sent_back_gate_can_be_put_back_in_play(self):
        self.reel.gates.get(step=Step.IDEA).decide(GateResult.AUTO, self.user)
        self.reel.gates.get(step=Step.HOOK).decide(GateResult.AUTO, self.user)
        board = self.reel.gates.get(step=Step.BOARD)
        board.decide(GateResult.REJECTED, self.user, "no beat in scene 2")

        response = self.client.post(
            self.gate_url(Step.BOARD), {"action": "reopen"}, follow=True
        )
        assert board.__class__.objects.get(pk=board.pk).result == GateResult.PENDING
        assert "back in play" in messages_of(response)[0]

    def test_the_detail_page_offers_the_decision_for_the_current_gate_only(self):
        body = self.client.get(self.detail).content.decode()
        assert "Spark" in body
        assert "Approve" not in body  # Spark passes on evidence, not a person
        assert "Mark passed" in body
        assert body.count('name="action"') == 1


class DeleteTests(ReelViewTestCase):
    def test_deleting_a_reel_takes_its_gates_with_it(self):
        gate_ids = list(self.reel.gates.values_list("pk", flat=True))
        response = self.client.post(reverse("reel_delete", args=[self.reel.pk]))
        assert response.status_code == 302
        assert response["Location"] == reverse("campaign_detail", args=[self.campaign.pk])
        assert not Reel.objects.filter(pk=self.reel.pk).exists()
        from apps.instagram.models import ReelGate

        assert not ReelGate.objects.filter(pk__in=gate_ids).exists()

    def test_delete_is_post_only(self):
        response = self.client.get(reverse("reel_delete", args=[self.reel.pk]))
        assert response.status_code == 405


class ListTests(ReelViewTestCase):
    def test_the_list_shows_reels_with_their_campaign_and_project(self):
        body = self.client.get(reverse("reels")).content.decode()
        assert "Flying Eyes" in body
        assert "Launch" in body
        assert "Works" in body
        assert "On Spark" in body

    def test_another_organizations_reel_stays_out(self):
        outsider = make_user("otto")
        other = make_org(outsider, name="Other")
        theirs_campaign = make_campaign(other, title="Theirs")
        Reel.start(campaign=theirs_campaign, title="Theirs", slug="theirs")
        self.client.force_login(outsider)

        body = self.client.get(reverse("reels")).content.decode()
        assert "Theirs" in body
        assert "Flying Eyes" not in body

    def test_the_empty_state_points_at_campaigns(self):
        Reel.objects.all().delete()
        body = self.client.get(reverse("reels")).content.decode()
        assert "No reels yet" in body
        assert "Open a campaign" in body
