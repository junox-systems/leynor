"""The state machine: six gates, locks, attempts, rewind."""

import pytest

from reel_playbook import ReelPlaybook, StateError
from reel_playbook.storage import Workspace


@pytest.fixture
def ws(tmp_path):
    return Workspace(tmp_path / "ws")


@pytest.fixture
def book(ws):
    return ReelPlaybook.create(ws, "ep-01")


def test_create_writes_db_row_and_manifest(ws, book):
    assert ws.catalog().get_project("ep-01")["state"] == "IDEA"
    payload = book.manifest()
    assert payload["slug"] == "ep-01"
    assert payload["state"] == "IDEA"
    assert payload["tokens"]["fps"] == 30


def test_create_refuses_existing_slug(ws, book):
    with pytest.raises(StateError):
        ReelPlaybook.create(ws, "ep-01")


def test_open_missing_project(ws):
    with pytest.raises(StateError):
        ReelPlaybook.open(ws, "nope")


def test_gate_order_is_enforced(book):
    with pytest.raises(StateError):
        book.pass_gate("voice", "too early")


def test_pass_requires_evidence(book):
    with pytest.raises(StateError):
        book.pass_gate("idea", "   ")


def test_pass_moves_state_and_persists(ws, book):
    assert book.pass_gate("idea", "one sentence, goal saves") == "HOOK"
    reopened = ReelPlaybook.open(ws, "ep-01")
    assert reopened.state == "HOOK"
    assert reopened.gates["idea"].evidence == "one sentence, goal saves"


def test_fail_keeps_state_and_counts(ws, book):
    book.pass_gate("idea", "ok")
    book.fail_gate("hook", "no payoff")
    reopened = ReelPlaybook.open(ws, "ep-01")
    assert reopened.state == "HOOK"
    assert reopened.gates["hook"].attempts == 1


def test_three_failures_stop(book):
    book.fail_gate("idea", "no insight")
    book.fail_gate("idea", "still no insight")
    with pytest.raises(StateError):
        book.fail_gate("idea", "no insight")
    assert book.gates["idea"].attempts == 3
    with pytest.raises(StateError):
        book.fail_gate("idea", "again")


def test_voice_locks_need_tokens(book):
    for step in ("idea", "hook", "board", "look"):
        book.pass_gate(step, "ok")
    with pytest.raises(StateError):
        book.pass_gate("voice", "no voice set")


def test_voice_pass_locks_voice_and_duration(ws, book):
    for step in ("idea", "hook", "board", "look"):
        book.pass_gate(step, "ok")
    book.set_token("voice", "fantine")
    book.set_token("duration", 12.5)
    book.pass_gate("voice", "one master")
    reopened = ReelPlaybook.open(ws, "ep-01")
    assert reopened.locked_at["voice"] == "PRINT"
    assert reopened.locked_at["duration"] == "PRINT"
    with pytest.raises(StateError):
        reopened.set_token("voice", "alba")


def test_spec_tokens_are_frozen(book):
    with pytest.raises(StateError):
        book.set_token("fps", 24)


def test_rewind_drops_gates_and_locks(ws, book):
    book.pass_gate("idea", "ok")
    book.pass_gate("hook", "ok")
    assert book.rewind("idea", "new angle") == "IDEA"
    reopened = ReelPlaybook.open(ws, "ep-01")
    assert reopened.state == "IDEA"
    assert reopened.gates == {}


def test_rewind_cannot_go_forward(book):
    with pytest.raises(StateError):
        book.rewind("voice", "nope")


def test_rewind_to_voice_clears_cues(book):
    for step in ("idea", "hook", "board", "look"):
        book.pass_gate(step, "ok")
    book.catalog.put_cues(
        book.slug,
        [{"scene": 1, "start": 0.0, "end": 1.0, "text": "one"}],
    )
    book.save()
    assert len(book.cues()) == 1
    book.rewind("voice", "word changed")
    assert book.cues() == []


def test_flow_progress_and_status(book):
    book.pass_gate("idea", "ok")
    flow = book.flow()
    assert flow.progress == pytest.approx(1 / 6, abs=1e-3)
    assert flow.current.id == "hook"
    report = book.status(logs=10)
    assert report.project == "ep-01"
    assert report.state == "HOOK"
    assert [entry.action for entry in report.logs][-2:] == ["init", "pass"]


def test_status_artifacts_come_from_the_db(book):
    flow = book.flow()
    assert "STORYBOARD.md" in flow.steps[2].artifacts
    assert flow.steps[2].artifacts["STORYBOARD.md"] is False
    book.put_text("STORYBOARD.md", "# STORYBOARD\n")
    assert book.flow().steps[2].artifacts["STORYBOARD.md"] is True
    assert not (book.root / "STORYBOARD.md").exists()


def test_repr(book):
    assert "ep-01" in repr(book)
