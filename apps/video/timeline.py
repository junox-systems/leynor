"""Timeline gate: master take, cue map, composition and render must agree.

The master voice is the clock. Cues are checked for coverage and sanity, then the
composition and mp4 are compared to the master duration within one frame.
"""

import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field


class TimelineReport(BaseModel):
    ok: bool
    fps: float
    tolerance: float
    duration: float = 0.0
    video_duration: float | None = None
    video_fps: float | None = None
    cues: int = 0
    last_cue_end: float | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TimelineError(RuntimeError):
    pass


DATA_DURATION = re.compile(r"""data-duration\s*=\s*["']([0-9.]+)["']""")


def check_summary(output: str) -> tuple[int, int]:
    """Read the `N error(s), M warning(s)` line; silence is a failure."""
    match = re.search(r"(\d+) error\(s\), (\d+) warning\(s\)", output)
    if not match:
        raise TimelineError("hyperframes check printed no summary line")
    return int(match.group(1)), int(match.group(2))


def probe_duration(path: Path) -> float | None:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        return None
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def probe_fps(path: Path) -> float | None:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        return None
    try:
        num, _, den = out.stdout.strip().partition("/")
        return float(num) / float(den or 1)
    except ValueError:
        return None


def check_timeline(
    root: Path,
    cues: list[dict],
    *,
    fps: float = 30.0,
    tolerance_frames: int = 1,
    duration: float | None = None,
    video: Path | None = None,
    master: Path | None = None,
    index_html: str | None = None,
) -> TimelineReport:
    tolerance = tolerance_frames / fps
    report = TimelineReport(ok=False, fps=fps, tolerance=tolerance)
    master = master or root / "assets" / "voice.wav"
    if not master.exists():
        report.errors.append(f"missing {master}")
        return report

    measured = probe_duration(master)
    if measured is None:
        report.errors.append(f"unreadable {master}")
        return report
    report.duration = round(measured, 3)

    if not cues:
        report.errors.append("no cues; run the aligner")
    else:
        report.cues = len(cues)
        report.last_cue_end = round(max(float(c["end"]) for c in cues), 3)
        previous_end = 0.0
        for index, cue in enumerate(cues, start=1):
            start, end = float(cue["start"]), float(cue["end"])
            if end <= start:
                report.errors.append(f"cue {index}: end {end} <= start {start}")
            if start < previous_end - 0.05:
                report.errors.append(f"cue {index}: overlaps or runs backwards")
            if end - start > 6.5:
                report.errors.append(f"cue {index}: {end - start:.2f}s is too long")
            if start > report.duration + tolerance:
                report.errors.append(f"cue {index}: starts after the master ends")
            if not str(cue.get("text", "")).strip():
                report.errors.append(f"cue {index}: empty text")
            previous_end = max(previous_end, end)
        if (
            report.last_cue_end is not None
            and report.last_cue_end > report.duration + tolerance
        ):
            report.errors.append(
                f"last cue ends at {report.last_cue_end:.3f}s, master is "
                f"{report.duration:.3f}s"
            )

    if duration is not None and abs(duration - report.duration) > tolerance:
        report.errors.append(
            f"locked duration {duration}s differs from master {report.duration:.3f}s"
        )

    index = root / "index.html"
    html = (
        index_html
        if index_html is not None
        else (index.read_text() if index.exists() else None)
    )
    if html is not None:
        match = DATA_DURATION.search(html)
        if not match:
            report.errors.append("index.html has no data-duration")
        else:
            root_duration = float(match.group(1))
            if abs(root_duration - report.duration) > tolerance:
                report.errors.append(
                    f"data-duration {root_duration:.3f}s differs from master "
                    f"{report.duration:.3f}s by more than {tolerance:.3f}s"
                )
    else:
        report.warnings.append("no index.html yet (step 6 writes it)")

    if video is not None:
        path = video if video.is_absolute() else root / video
        report.video_duration = probe_duration(path) if path.exists() else None
        report.video_fps = probe_fps(path) if path.exists() else None
        if report.video_duration is None:
            report.errors.append(f"missing or unreadable video {path}")
        else:
            if abs(report.video_duration - report.duration) > tolerance:
                report.errors.append(
                    f"video is {report.video_duration:.3f}s, master is "
                    f"{report.duration:.3f}s"
                )
            if report.video_fps is None or abs(report.video_fps - fps) > 0.01:
                report.errors.append(
                    f"video is {report.video_fps}fps, expected {fps:g}fps"
                )

    report.ok = not report.errors
    return report
