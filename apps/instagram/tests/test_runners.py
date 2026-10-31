"""Registry: every step resolves, and resolving one loads no heavy module."""

import sys

import pytest

from apps.instagram.gates import Step
from apps.instagram.runners import NoRunner, RUNNERS, runner


def test_every_step_has_a_runner():
    assert set(RUNNERS) == set(Step)


def test_runner_resolves_the_owning_app_function():
    assert runner(Step.IDEA).__name__ == "draft_step"
    assert runner(Step.VOICE).__name__ == "run_voice"
    assert runner(Step.PRINT).__name__ == "run_print"


def test_unknown_step_is_reported():
    with pytest.raises(NoRunner):
        runner("render")


def test_importing_the_registry_loads_no_heavy_module():
    for module in ("torch", "faster_whisper", "pocket_tts"):
        assert module not in sys.modules, module
