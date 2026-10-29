"""The web process must never load torch, whisper, or the TTS model."""

import subprocess
import sys
from pathlib import Path

HEAVY = ("torch", "faster_whisper", "pocket_tts")


def test_importing_the_urlconf_loads_no_media_dependency():
    root = Path(__file__).resolve().parents[1]
    script = (
        "import os, sys;"
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.test');"
        "import django;django.setup();"
        "import config.urls;"
        "print(','.join(sorted(m for m in {mods!r} if m in sys.modules)))".format(
            mods=HEAVY
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "", f"heavy modules imported: {result.stdout}"
