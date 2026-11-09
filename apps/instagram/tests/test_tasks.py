"""The route runs itself: pitch, pick, then steps until a person or a fault stops it.

Tests run django-q2 inline (`sync: True`), so queueing a task runs it.
"""

from unittest import mock

from django.test import TestCase

from apps.brands.models import Audience, Brand
from apps.instagram import services, tasks
from apps.instagram.gates import GateResult, Step
from apps.instagram.models import Reel, ReelPitch, RunStatus
from apps.instagram.tests import fakes
from apps.instagram.tests.test_views import make_campaign, make_org, make_user


class RouteTaskTestCase(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.org = make_org(self.user)
        self.campaign = make_campaign(self.org)
        self.pitch = ReelPitch.objects.create(
            campaign=self.campaign, idea="Why habits die on day three", goal="saves"
        )

    def pitched(self, text=None):
        with (text or fakes.FakeText()).patch():
            tasks.queue_pitch(self.pitch)
        self.pitch.refresh_from_db()
        return self.pitch

    def picked(self, text=None):
        self.pitched()
        text = text or fakes.FakeText()
        with text.patch():
            reel, _ = self.pitch.pick(round_index=0, concept_index=1, user=self.user)
            tasks.queue_advance(reel)
        return Reel.objects.get(pk=reel.pk)


class PitchTaskTests(RouteTaskTestCase):
    def test_a_pitch_becomes_one_round_of_three_checked_concepts(self):
        pitch = self.pitched()
        assert pitch.status == ReelPitch.Status.READY
        assert len(pitch.rounds) == 1
        assert [c["title"] for c in pitch.latest["concepts"]] == [
            "Take number 1",
            "Take number 2",
            "Take number 3",
        ]

    def test_citing_an_audience_the_campaign_lacks_fails_after_one_redraft(self):
        text = fakes.FakeText(
            concepts=[fakes.concept(n, source="audience") for n in (1, 2, 3)]
        )
        pitch = self.pitched(text)
        assert pitch.status == ReelPitch.Status.FAILED
        assert "cites an audience, but the campaign has none" in pitch.error
        assert len(text.briefs) == 2  # one draft, one redraft told what failed
        assert "failed these checks" in text.briefs[1][1]

    def test_the_brief_carries_the_audience_and_never_invites_invention(self):
        brand = Brand.objects.create(organization=self.org, name="Habitly")
        self.campaign.audience = Audience.objects.create(
            brand=brand, name="New runners", wants="a streak", barrier="sore legs"
        )
        self.campaign.save()
        text = fakes.FakeText()
        self.pitched(text)
        brief = text.briefs[0][1]
        assert "Audience: New runners" in brief
        assert "They want: a streak" in brief
        assert "Never invent" in brief

    def test_a_new_round_remembers_what_was_offered_and_the_note(self):
        self.pitched()
        self.pitch.start("shorter, funnier")
        text = fakes.FakeText()
        self.pitched(text)
        brief = text.briefs[0][1]
        assert "Round 1 offered: Take number 1" in brief
        assert "shorter, funnier" in brief
        assert len(self.pitch.rounds) == 2
        assert self.pitch.rounds[1]["feedback"] == "shorter, funnier"

    def test_a_model_fault_stops_the_pitch_with_its_reason(self):
        pitch = self.pitched(fakes.FakeText(fail_on=services.ConceptSet))
        assert pitch.status == ReelPitch.Status.FAILED
        assert "model unavailable" in pitch.error


class AdvanceTaskTests(RouteTaskTestCase):
    def test_a_pick_runs_hook_and_stops_at_the_board_for_a_person(self):
        reel = self.picked()
        gates = {gate.step: gate for gate in reel.gates.all()}
        assert gates["idea"].result == GateResult.APPROVED
        assert gates["idea"].decided_by == self.user
        assert gates["hook"].result == GateResult.AUTO
        assert gates["board"].result == GateResult.PENDING
        assert gates["board"].awaiting_person
        assert reel.spec["kicker"] == self.campaign.title.upper()
        assert len(reel.spec["scenes"]) == 4

    def test_the_picked_hook_stays_the_winner(self):
        reel = self.picked()
        hooks = reel.gates.get(step=Step.HOOK).output["hooks"]
        winners = [hook for hook in hooks if hook["chosen"]]
        assert [hook["spoken"] for hook in winners] == ["Motivation is a trap, take 2."]

    def test_approving_the_board_runs_look_and_voice_and_stops_at_print(self):
        reel = self.picked()
        voice, print_ = fakes.engines()
        with voice, print_:
            reel.gates.get(step=Step.BOARD).decide(GateResult.APPROVED, self.user)
            tasks.queue_advance(reel)
        gates = {gate.step: gate for gate in reel.gates.all()}
        assert len(gates["look"].output["visuals"]) == 4
        assert reel.store().exists("assets/visuals/s1.svg")
        assert gates["voice"].result == GateResult.AUTO
        assert gates["print"].awaiting_person
        assert reel.store().exists("out.mp4")

    def test_a_step_that_fails_stops_the_route_and_can_be_tried_again(self):
        self.pitched()
        with fakes.FakeText(fail_on=services.Board).patch():
            reel, _ = self.pitch.pick(round_index=0, concept_index=0, user=self.user)
            tasks.queue_advance(reel)
        board = reel.gates.get(step=Step.BOARD)
        assert board.status == RunStatus.FAILED
        assert "model unavailable" in board.error
        assert reel.needs_person

        with fakes.FakeText().patch():
            board.retry()
            tasks.queue_advance(reel)
        board.refresh_from_db()
        assert board.status == RunStatus.IDLE
        assert board.awaiting_person

    def test_a_send_back_reruns_the_step_with_the_note(self):
        reel = self.picked()
        board = reel.gates.get(step=Step.BOARD)
        board.decide(GateResult.REJECTED, self.user, "less jargon")
        text = fakes.FakeText()
        with text.patch():
            tasks.queue_advance(reel)
        board.refresh_from_db()
        assert board.result == GateResult.PENDING
        assert board.awaiting_person
        assert "less jargon" in text.briefs[-1][1]

    def test_a_step_already_running_is_not_run_twice(self):
        reel = self.picked()
        board = reel.gates.get(step=Step.BOARD)
        board.decide(GateResult.REJECTED, self.user, "again")
        board.status = RunStatus.RUNNING
        board.save()
        with mock.patch.object(tasks, "runner") as runner:
            tasks.advance(str(reel.pk))
        runner.assert_not_called()

    def test_a_reel_deleted_while_queued_is_ignored(self):
        reel = self.picked()
        reel_id = str(reel.pk)
        reel.delete()
        tasks.advance(reel_id)  # no error

    def test_heavy_steps_go_to_the_heavy_cluster(self):
        reel = self.picked()
        reel.gates.get(step=Step.BOARD).decide(GateResult.APPROVED, self.user)
        reel.gates.get(step=Step.LOOK).decide(GateResult.AUTO, None)
        with mock.patch.object(tasks, "async_task") as queued:
            tasks.queue_advance(reel)
        assert queued.call_args.kwargs["cluster"].endswith("-heavy")


class ArtifactTests(RouteTaskTestCase):
    def test_print_refuses_inputs_that_changed_or_vanished(self):
        store = self.picked().store()
        sha = store.put("assets/visuals/s1.svg", "<svg/>")
        services._verify(store, {"assets/visuals/s1.svg": sha})  # unchanged: passes

        store.put("assets/visuals/s1.svg", "<svg>edited</svg>")
        with self.assertRaisesMessage(services.StepFailed, "s1.svg changed since it was checked"):
            services._verify(store, {"assets/visuals/s1.svg": sha})
        with self.assertRaisesMessage(services.StepFailed, "assets/voice.wav is missing"):
            services._verify(store, {services.VOICE_KEY: sha})

    def test_print_refuses_a_voice_that_changed_after_voice_checked_it(self):
        reel = self.picked()
        voice, print_ = fakes.engines()
        with voice, print_:
            reel.gates.get(step=Step.BOARD).decide(GateResult.APPROVED, self.user)
            tasks.queue_advance(reel)  # Look runs for real

        def run_voice(spec, store):
            store.put(services.VOICE_KEY, b"RIFF voice")
            return mock.Mock(
                max_silence=0.2,
                loudness=-14.0,
                model_dump=lambda: {"cues": [], "duration": 61.0, "loudness": -14.0},
            )

        with mock.patch("apps.video.audio.services.run_voice", run_voice):
            output = services.voice_step(reel)
        gate = reel.gates.get(step=Step.VOICE)
        gate.output = output
        gate.save()

        with (
            mock.patch("apps.video.services.run_compose", return_value=[]) as compose,
            mock.patch("apps.video.services.run_print") as print_,
        ):
            services.print_step(reel)  # unchanged: renders
            assert print_.called

            reel.store().put(services.VOICE_KEY, b"RIFF edited")
            compose.reset_mock()
            with self.assertRaisesMessage(services.StepFailed, "voice.wav changed"):
                services.print_step(reel)
            gate.output = {k: v for k, v in output.items() if k != "sha"}
            gate.save()
            with self.assertRaisesMessage(services.StepFailed, "Run Look or Voice again"):
                services.print_step(reel)
            compose.assert_not_called()

    def test_deleting_a_reel_deletes_its_files_after_commit(self):
        reel = self.picked()
        store = reel.store()
        store.put("out.mp4", b"mp4")
        with self.captureOnCommitCallbacks(execute=True):
            reel.delete()
        assert not store.exists("out.mp4")
