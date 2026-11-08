import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.campaigns.models import Campaign
from apps.instagram.gates import GateResult, Step
from apps.instagram.models import GateOutOfOrder, Reel
from apps.orgs import rbac
from apps.orgs.models import OWNER, Membership, Organization, Role
from apps.projects.models import Project
from apps.users.models import User


def make_org(user, name="Acme"):
    org = Organization.objects.create(name=name)
    membership = Membership.objects.create(organization=org, user=user)
    membership.roles.add(Role.objects.get(name=OWNER))
    return org


def make_campaign(org, title="Launch"):
    project = Project.create(organization=org, title=f"Works {title}")
    return Campaign.objects.create(project=project, title=title)


class RouteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@example.com", username="a", password="pw"
        )
        self.org = make_org(self.user)
        self.campaign = make_campaign(self.org)
        self.reel = Reel.create(
            campaign=self.campaign, title="Flying Eyes", slug="flying-eyes"
        )

    def test_create_makes_one_gate_per_step_in_route_order(self):
        gates = list(self.reel.gates.all())
        assert [gate.step for gate in gates] == [step.value for step in Step]
        assert [gate.position for gate in gates] == list(range(6))
        assert {gate.step for gate in gates if gate.kind == "human"} == {
            "idea",
            "board",
            "print",
        }

    def test_current_gate_walks_the_route_as_gates_pass(self):
        assert self.reel.current_gate.step == Step.IDEA.value
        self.reel.gates.get(step=Step.IDEA).decide(GateResult.AUTO, self.user)
        assert self.reel.current_gate.step == Step.HOOK.value
        assert self.reel.passed == 1
        assert self.reel.percent == 17

    def test_only_the_current_gate_can_be_decided(self):
        hook = self.reel.gates.get(step=Step.HOOK)
        with pytest.raises(GateOutOfOrder):
            hook.decide(GateResult.AUTO, self.user)
        assert hook.result == GateResult.PENDING

    def test_sending_back_keeps_the_route_there_and_reopen_resets_it(self):
        self.reel.gates.get(step=Step.IDEA).decide(GateResult.AUTO, self.user)
        self.reel.gates.get(step=Step.HOOK).decide(GateResult.AUTO, self.user)
        board = self.reel.gates.get(step=Step.BOARD)
        board.decide(GateResult.REJECTED, self.user, "Scene two has no visual beat")

        assert self.reel.current_gate.pk == board.pk
        assert self.reel.needs_person is False  # the redo runs; nobody waits on it
        assert board.note == "Scene two has no visual beat"
        assert [row["state"] for row in self.reel.route()][2] == "rejected"

        board.reopen()
        assert board.result == GateResult.PENDING
        assert board.decided_by is None
        assert board.note == ""

    def test_a_reel_is_complete_once_every_gate_has_passed(self):
        for step in Step:
            self.reel.gates.get(step=step).decide(GateResult.APPROVED, self.user)
        assert self.reel.complete is True
        assert self.reel.current_gate is None
        assert self.reel.percent == 100
        assert self.reel.summary() == "Complete"

    def test_route_rows_carry_the_copy_the_template_prints(self):
        rows = self.reel.route()
        assert [row["name"] for row in rows][:2] == ["Spark", "Hook"]
        assert rows[0]["state"] == "current"
        assert rows[0]["label"] == "Your call"
        assert rows[1]["state"] == "waiting"

    def test_slugs_are_unique_per_campaign(self):
        with pytest.raises(IntegrityError):
            Reel.create(campaign=self.campaign, title="Other", slug="flying-eyes")

    def test_the_same_slug_is_free_in_another_campaign(self):
        other = make_campaign(self.org, title="Second")
        reel = Reel.create(campaign=other, title="Flying Eyes", slug="flying-eyes")
        assert reel.gates.count() == 6

    def test_tenancy_resolves_through_the_campaign(self):
        assert self.reel.organization == self.org
        assert self.campaign.organization == self.org
        # rbac.check_access reads exactly this attribute; None would deny.
        assert rbac._organization_of(self.reel) == self.org

    def test_the_spec_is_validated_when_present(self):
        self.reel.spec = {
            "slug": "flying-eyes",
            "title": "Flying Eyes",
            "scenes": [
                {"narration": "One line.", "overlay": "One", "label": "a"},
                {"narration": "Two lines.", "overlay": "Two", "label": "b"},
            ],
        }
        self.reel.full_clean()

        self.reel.spec = {"slug": "flying-eyes", "title": "Broken", "scenes": []}
        with pytest.raises(ValidationError):
            self.reel.full_clean()


class RunStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@example.com", username="a", password="pw"
        )
        self.reel = Reel.create(
            campaign=make_campaign(make_org(self.user)), title="Flying Eyes"
        )
        self.reel.gates.get(step=Step.IDEA).decide(GateResult.APPROVED, self.user)
        self.hook = self.reel.gates.get(step=Step.HOOK)

    def test_a_gate_is_claimed_once(self):
        assert self.hook.claim() is True
        assert self.reel.gates.get(step=Step.HOOK).claim() is False

    def test_running_failing_and_retrying_show_on_the_route(self):
        self.hook.claim()
        assert self.reel.route()[1]["state"] == "running"
        assert self.reel.summary() == "Running Hook"
        self.hook.fail("overlay too long")
        assert self.reel.route()[1]["state"] == "failed"
        assert self.reel.needs_person is True
        self.hook.retry()
        assert self.reel.route()[1]["state"] == "queued"
        with pytest.raises(ValidationError):
            self.hook.retry()

    def test_a_redo_after_a_send_back_is_judged_again(self):
        self.hook.decide(GateResult.AUTO, self.user)
        board = self.reel.gates.get(step=Step.BOARD)
        board.finish({"scenes": [1]})
        assert board.awaiting_person
        board.decide(GateResult.REJECTED, self.user, "less jargon")
        assert not board.awaiting_person
        board.finish({"scenes": [2]})
        assert board.result == GateResult.PENDING
        assert board.decided_by is None
        assert board.awaiting_person


class PitchModelTests(TestCase):
    def setUp(self):
        from apps.instagram.models import ReelPitch

        self.user = User.objects.create_user(
            email="a@example.com", username="a", password="pw"
        )
        self.pitch = ReelPitch.objects.create(
            campaign=make_campaign(make_org(self.user)), idea="An idea", goal="shares",
            rounds=[{"feedback": "", "concepts": [{"title": f"Take {n}"} for n in (1, 2, 3)]}],
            status="ready",
        )

    def test_a_pick_records_the_choice_and_the_rest_as_alternatives(self):
        reel, created = self.pitch.pick(round_index=0, concept_index=1, user=self.user, note="warm")
        assert created and reel.title == "Take 2" and reel.goal == "shares"
        spark = reel.gates.get(step=Step.IDEA)
        assert spark.result == GateResult.APPROVED
        assert [a["title"] for a in spark.output["alternatives"]] == ["Take 1", "Take 3"]
        again, created = self.pitch.pick(round_index=0, concept_index=0, user=self.user)
        assert again == reel and created is False

    def test_a_concept_that_is_not_there_is_refused(self):
        from apps.instagram.models import PitchError

        with pytest.raises(PitchError):
            self.pitch.pick(round_index=3, concept_index=0, user=self.user)
