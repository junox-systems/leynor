from unittest import mock

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.campaigns.models import Campaign
from apps.instagram.gates import GateResult, Step
from apps.instagram.models import Reel, ReelPitch, RunStatus
from apps.instagram.tests import fakes
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
    project = Project.create(organization=org, title=f"Works {title}")
    return Campaign.objects.create(project=project, title=title)


def messages_of(response):
    return [message.message for message in get_messages(response.wsgi_request)]


class ReelViewTestCase(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.org = make_org(self.user)
        self.campaign = make_campaign(self.org)
        self.reel = Reel.create(
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
        theirs = Reel.create(campaign=theirs_campaign, title="Theirs", slug="theirs")
        self.client.force_login(outsider)

        assert (
            self.client.get(reverse("reel_detail", args=[theirs.pk])).status_code == 200
        )
        assert self.client.get(self.detail).status_code == 404


class IdeaToReelTests(ReelViewTestCase):
    def submit_idea(self, **data):
        payload = {"idea": "Why habits die on day three", "goal": "saves", "target_seconds": 60}
        payload.update(data)
        with fakes.FakeText().patch():
            return self.client.post(reverse("reel_new", args=[self.campaign.pk]), payload)

    def test_the_idea_form_asks_for_an_idea_a_goal_and_a_length(self):
        body = self.client.get(reverse("reel_new", args=[self.campaign.pk])).content.decode()
        assert "Start from an idea" in body
        assert 'name="goal"' in body and 'value="follows"' in body
        assert 'name="target_seconds"' in body
        assert "This campaign has no audience" in body

    def test_an_idea_becomes_a_pitch_with_three_takes(self):
        response = self.submit_idea()
        pitch = ReelPitch.objects.get()
        assert response["Location"] == reverse("reel_pitch", args=[pitch.pk])
        body = self.client.get(response["Location"]).content.decode()
        assert "Pick the take to build" in body
        assert body.count('name="concept"') == 3
        assert "Take 1 of 3" in body
        assert "Motivation is a trap" in body
        assert "Instagram caption" in body  # the safe-zone guide

    def test_a_length_outside_the_choices_is_refused(self):
        for seconds in (30, 240):
            response = self.submit_idea(target_seconds=seconds)
            assert response.status_code == 200
        assert not ReelPitch.objects.exists()

    def test_picking_a_take_makes_the_reel_and_runs_to_the_board(self):
        self.submit_idea()
        pitch = ReelPitch.objects.get()
        with fakes.FakeText().patch():
            response = self.client.post(
                reverse("reel_pitch_decide", args=[pitch.pk]),
                {"action": "pick", "concept": "0:2", "note": "keep it warm"},
            )
        reel = Reel.objects.get(title="Take number 3")
        assert response["Location"] == reverse("reel_detail", args=[reel.pk])
        assert reel.slug == "take-number-3"
        assert reel.prompt == "Why habits die on day three"
        spark = reel.gates.get(step=Step.IDEA)
        assert spark.result == GateResult.APPROVED
        assert spark.output["note"] == "keep it warm"
        body = self.client.get(response["Location"]).content.decode()
        assert "Approve the board" in body
        assert "Your note:" in body

    def test_picking_twice_makes_one_reel(self):
        self.submit_idea()
        pitch = ReelPitch.objects.get()
        url = reverse("reel_pitch_decide", args=[pitch.pk])
        with fakes.FakeText().patch():
            for _ in range(2):
                self.client.post(url, {"action": "pick", "concept": "0:0"})
        assert Reel.objects.filter(title="Take number 1").count() == 1
        pitch.refresh_from_db()
        response = self.client.get(reverse("reel_pitch", args=[pitch.pk]))
        assert response["Location"] == reverse("reel_detail", args=[pitch.reel_id])

    def test_picking_nothing_is_refused_with_a_message(self):
        self.submit_idea()
        pitch = ReelPitch.objects.get()
        response = self.client.post(
            reverse("reel_pitch_decide", args=[pitch.pk]), {"action": "pick"}, follow=True
        )
        assert messages_of(response) == ["Choose one of the takes first."]

    def test_three_new_takes_keep_the_earlier_round(self):
        self.submit_idea()
        pitch = ReelPitch.objects.get()
        with fakes.FakeText().patch():
            self.client.post(
                reverse("reel_pitch_decide", args=[pitch.pk]),
                {"action": "again", "note": "funnier"},
            )
        pitch.refresh_from_db()
        assert len(pitch.rounds) == 2
        body = self.client.get(reverse("reel_pitch", args=[pitch.pk])).content.decode()
        assert "Earlier takes (1 round)" in body
        assert "after your note: “funnier”" in body
        assert body.count('name="concept"') == 6

    def test_another_organizations_pitch_is_a_404(self):
        self.submit_idea()
        pitch = ReelPitch.objects.get()
        self.client.force_login(make_user("otto"))
        make_org(User.objects.get(username="otto"), name="Other")
        assert self.client.get(reverse("reel_pitch", args=[pitch.pk])).status_code == 404


class GateTests(ReelViewTestCase):
    def run_to_board(self):
        for step in (Step.IDEA, Step.HOOK):
            self.reel.gates.get(step=step).decide(GateResult.APPROVED, self.user)
        board = self.reel.gates.get(step=Step.BOARD)
        board.finish({"scenes": []})
        return board

    def test_a_board_waiting_for_a_person_can_be_approved(self):
        board = self.run_to_board()
        with mock.patch("apps.instagram.views.queue_advance") as queued:
            response = self.client.post(self.gate_url(Step.BOARD), {"action": "approve"}, follow=True)
        board.refresh_from_db()
        assert board.result == GateResult.APPROVED
        assert board.decided_by == self.user
        assert messages_of(response) == ["Board approved."]
        queued.assert_called_once()

    def test_sending_back_needs_a_note(self):
        board = self.run_to_board()
        response = self.client.post(self.gate_url(Step.BOARD), {"action": "reject"}, follow=True)
        board.refresh_from_db()
        assert board.result == GateResult.PENDING
        assert "Say what Board should change" in messages_of(response)[0]

    def test_sending_back_with_a_note_queues_the_redo(self):
        board = self.run_to_board()
        with mock.patch("apps.instagram.views.queue_advance") as queued:
            self.client.post(self.gate_url(Step.BOARD), {"action": "reject", "note": "less jargon"})
        board.refresh_from_db()
        assert board.result == GateResult.REJECTED
        assert board.note == "less jargon"
        queued.assert_called_once()

    def test_a_step_that_passes_on_checks_cannot_be_clicked_through(self):
        self.reel.gates.get(step=Step.IDEA).decide(GateResult.APPROVED, self.user)
        response = self.client.post(self.gate_url(Step.HOOK), {"action": "approve"}, follow=True)
        assert self.reel.gates.get(step=Step.HOOK).result == GateResult.PENDING
        assert "passes on its checks" in messages_of(response)[0]

    def test_a_board_with_nothing_to_judge_is_refused(self):
        for step in (Step.IDEA, Step.HOOK):
            self.reel.gates.get(step=step).decide(GateResult.APPROVED, self.user)
        response = self.client.post(self.gate_url(Step.BOARD), {"action": "approve"}, follow=True)
        assert "nothing to decide yet" in messages_of(response)[0]

    def test_a_stopped_step_shows_its_reason_and_a_retry(self):
        self.reel.gates.get(step=Step.IDEA).decide(GateResult.APPROVED, self.user)
        hook = self.reel.gates.get(step=Step.HOOK)
        hook.claim()
        hook.fail("hook 2 overlay is over 44 characters")
        body = self.client.get(self.detail).content.decode()
        assert "Hook stopped" in body
        assert "hook 2 overlay is over 44 characters" in body
        with mock.patch("apps.instagram.views.queue_advance") as queued:
            self.client.post(reverse("step_retry", args=[self.reel.pk, "hook"]))
        hook.refresh_from_db()
        assert hook.status == RunStatus.IDLE
        queued.assert_called_once()

    def test_a_legacy_reel_offers_spark_to_a_person(self):
        body = self.client.get(self.detail).content.decode()
        assert body.count('value="approve"') == 1
        assert 'value="reject"' not in body


class MediaTests(ReelViewTestCase):
    def setUp(self):
        super().setUp()
        self.reel.store().put("out.mp4", b"0123456789")
        self.url = reverse("reel_media", args=[self.reel.pk, "out.mp4"])

    def test_a_file_is_served_with_a_locked_down_policy(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == b"0123456789"
        assert response["Content-Type"] == "video/mp4"
        assert "default-src 'none'" in response["Content-Security-Policy"]

    def test_a_byte_range_is_a_206(self):
        response = self.client.get(self.url, headers={"Range": "bytes=2-5"})
        assert response.status_code == 206
        assert response.content == b"2345"
        assert response["Content-Range"] == "bytes 2-5/10"
        tail = self.client.get(self.url, headers={"Range": "bytes=-3"})
        assert tail.content == b"789"
        assert self.client.get(self.url, headers={"Range": "bytes=50-"}).status_code == 416

    def test_paths_outside_the_reel_and_other_tenants_are_404(self):
        escape = reverse("reel_media", args=[self.reel.pk, "../x"])
        assert self.client.get(escape).status_code == 404
        assert self.client.get(reverse("reel_media", args=[self.reel.pk, "nope.mp4"])).status_code == 404
        outsider = make_user("otto")
        make_org(outsider, name="Other")
        self.client.force_login(outsider)
        assert self.client.get(self.url).status_code == 404


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
        assert "Spark: your call" in body

    def test_another_organizations_reel_stays_out(self):
        outsider = make_user("otto")
        other = make_org(outsider, name="Other")
        theirs_campaign = make_campaign(other, title="Theirs")
        Reel.create(campaign=theirs_campaign, title="Theirs", slug="theirs")
        self.client.force_login(outsider)

        body = self.client.get(reverse("reels")).content.decode()
        assert "Theirs" in body
        assert "Flying Eyes" not in body

    def test_the_empty_state_points_at_campaigns(self):
        Reel.objects.all().delete()
        body = self.client.get(reverse("reels")).content.decode()
        assert "No reels yet" in body
        assert "Open a campaign" in body
