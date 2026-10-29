import pytest

from apps.projects.gates import Step, next_step, needs_human


def test_route_order_is_definition_order():
    assert [step.value for step in Step] == [
        "idea",
        "hook",
        "board",
        "look",
        "voice",
        "print",
    ]


def test_board_and_print_need_a_person():
    assert {step for step in Step if needs_human(step)} == {Step.BOARD, Step.PRINT}


def test_next_step_walks_the_route_and_stops_at_the_end():
    assert next_step(Step.IDEA) is Step.HOOK
    assert next_step(Step.VOICE) is Step.PRINT
    assert next_step(Step.PRINT) is None


def test_step_specs_are_indexed_by_step():
    from apps.projects.steps import STEPS, resolve

    assert [spec.id for spec in STEPS] == list(Step)
    assert resolve("idea").id is Step.IDEA
    assert resolve(Step.PRINT).id is Step.PRINT
    with pytest.raises(KeyError):
        resolve("render")
