import pytest
from django.db import IntegrityError
from django.test import TestCase

from apps.orgs.models import OWNER, Membership, Organization, Role
from apps.projects.gates import GateResult, Step
from apps.projects.models import Gate, GateOutOfOrder, Project
from apps.users.models import User


def make_org(user, name="Acme"):
    org = Organization.objects.create(name=name)
    membership = Membership.objects.create(organization=org, user=user)
    membership.roles.add(Role.objects.get(name=OWNER))
    return org


class RouteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@example.com", username="a", password="pw"
        )
        self.org = make_org(self.user)
        self.project = Project.start(
            organization=self.org, title="Flying Eyes", slug="flying-eyes"
        )

    def test_start_creates_one_gate_per_step_in_route_order(self):
        gates = list(self.project.gates.all())
        assert [gate.step for gate in gates] == [step.value for step in Step]
        assert [gate.position for gate in gates] == list(range(6))
        assert {gate.step for gate in gates if gate.kind == "human"} == {
            "board",
            "print",
        }

    def test_current_gate_walks_the_route_as_gates_pass(self):
        assert self.project.current_gate.step == Step.IDEA.value
        self.project.gates.get(step=Step.IDEA).decide(GateResult.AUTO, self.user)
        assert self.project.current_gate.step == Step.HOOK.value
        assert self.project.passed == 1
        assert self.project.percent == 17

    def test_only_the_current_gate_can_be_decided(self):
        hook = self.project.gates.get(step=Step.HOOK)
        with pytest.raises(GateOutOfOrder):
            hook.decide(GateResult.AUTO, self.user)
        assert hook.result == GateResult.PENDING

    def test_sending_back_keeps_the_route_there_and_reopen_resets_it(self):
        idea = self.project.gates.get(step=Step.IDEA)
        idea.decide(GateResult.AUTO, self.user)
        board = self.project.gates.get(step=Step.BOARD)
        self.project.gates.get(step=Step.HOOK).decide(GateResult.AUTO, self.user)
        board.decide(GateResult.REJECTED, self.user, "Scene two has no visual beat")

        assert self.project.current_gate.pk == board.pk
        assert self.project.needs_person is True
        assert board.note == "Scene two has no visual beat"
        assert [row["state"] for row in self.project.route()][2] == "rejected"

        board.reopen()
        assert board.result == GateResult.PENDING
        assert board.decided_by is None
        assert board.note == ""

    def test_a_reel_is_complete_once_every_gate_has_passed(self):
        for step in Step:
            self.project.gates.get(step=step).decide(GateResult.APPROVED, self.user)
        assert self.project.complete is True
        assert self.project.current_gate is None
        assert self.project.percent == 100
        assert self.project.summary() == "Complete"

    def test_route_rows_carry_the_copy_the_template_prints(self):
        rows = self.project.route()
        assert [row["name"] for row in rows][:2] == ["Spark", "Hook"]
        assert rows[0]["state"] == "current"
        assert rows[0]["variant"] == "outline"
        assert rows[1]["state"] == "waiting"

    def test_slugs_are_unique_per_organization(self):
        with pytest.raises(IntegrityError):
            Project.start(organization=self.org, title="Other", slug="flying-eyes")

    def test_the_same_slug_is_free_in_another_organization(self):
        other = make_org(
            User.objects.create_user(
                email="b@example.com", username="b", password="pw"
            ),
            name="Other",
        )
        project = Project.start(
            organization=other, title="Flying Eyes", slug="flying-eyes"
        )
        assert project.gates.count() == 6
        assert Gate.objects.filter(project=project).count() == 6
