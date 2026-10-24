"""Reel Playbook: one gated route from an idea to a rendered 9:16 Reel."""

from .align import AlignResult, FasterWhisper, cues_from_words, map_words, write_cues
from .book import ReelPlaybook, StateError
from .build import build, import_project
from .compose import compose, scene_windows
from .content import ReelSpec, SceneSpec, load_spec
from .creative import validate_beats, validate_hooks, validate_idea
from .design import Design, default_frame, parse_frame
from .imagetools import Procedural, Visual, Waveform, catalogue, get
from .models import (
    VERSION,
    Cue,
    DraftResult,
    FlowTracker,
    LogEntry,
    StatusReport,
    StepStatus,
    TimelineReport,
    Tokens,
)
from .steps import STEPS, StepSpec, resolve
from .storage import Catalog, Store, Workspace
from .timeline import check_timeline
from .tts import PocketTTS, TTSError
from .voice import MixReport, mix, synthesize_master

__version__ = VERSION

__all__ = [
    "AlignResult",
    "Catalog",
    "Cue",
    "Design",
    "DraftResult",
    "FasterWhisper",
    "FlowTracker",
    "LogEntry",
    "MixReport",
    "PocketTTS",
    "Procedural",
    "ReelPlaybook",
    "ReelSpec",
    "STEPS",
    "SceneSpec",
    "StateError",
    "StatusReport",
    "StepSpec",
    "StepStatus",
    "Store",
    "TTSError",
    "TimelineReport",
    "Tokens",
    "VERSION",
    "Visual",
    "Waveform",
    "Workspace",
    "build",
    "catalogue",
    "check_timeline",
    "compose",
    "cues_from_words",
    "default_frame",
    "get",
    "import_project",
    "load_spec",
    "map_words",
    "mix",
    "parse_frame",
    "resolve",
    "scene_windows",
    "synthesize_master",
    "validate_beats",
    "validate_hooks",
    "validate_idea",
    "write_cues",
]
