"""Measure a TTS wav: level, spectrum, prosody, pauses, clipping.

Usage:
    uv run --extra audit reel audit a.wav [b.wav ...]

Reports physics, not perceptual quality. Compare two files from the same text and
voice to see what a model swap changed.
"""

import sys

import librosa
import numpy as np
import soundfile as sf

HOP = 512


def load(path):
    y, sr = sf.read(path, dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    return y, sr


def db(x):
    return 20.0 * np.log10(max(float(x), 1e-12))


def pauses(y, sr, rel_db=-35.0):
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0]
    quiet = rms < rms.max() * (10 ** (rel_db / 20.0))
    runs, start = [], None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(quiet)))
    durs = [(b - a) * HOP / sr for a, b in runs]
    return [d for d in durs if d >= 0.08]


def audit(path):
    y, sr = load(path)
    peak = float(np.max(np.abs(y)))
    rms = float(np.sqrt(np.mean(y**2)))

    spectrum = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    power = spectrum**2

    def share(lo, hi):
        return float(power[(freqs >= lo) & (freqs < hi)].sum() / power.sum())

    f0, voiced, _ = librosa.pyin(
        y, fmin=60, fmax=500, sr=sr, frame_length=2048, hop_length=HOP
    )
    f0v = f0[voiced]
    semis = 12 * np.log2(f0v / np.median(f0v)) if len(f0v) else np.zeros(1)

    gaps = pauses(y, sr)

    return {
        "file": path.rsplit("/", 1)[-1],
        "dur_s": len(y) / sr,
        "peak_dbfs": db(peak),
        "rms_dbfs": db(rms),
        "crest_db": db(peak / max(rms, 1e-12)),
        "clipped": int(np.sum(np.abs(y) >= 0.999)),
        "centroid_hz": float(np.mean(librosa.feature.spectral_centroid(S=spectrum, sr=sr))),
        "rolloff85_hz": float(
            np.mean(librosa.feature.spectral_rolloff(S=spectrum, sr=sr, roll_percent=0.85))
        ),
        "flatness": float(np.mean(librosa.feature.spectral_flatness(S=spectrum))),
        "bandwidth_hz": float(np.mean(librosa.feature.spectral_bandwidth(S=spectrum, sr=sr))),
        "hf_8_12k": share(8000, 12000),
        "f0_hz": float(np.median(f0v)) if len(f0v) else 0.0,
        "f0_iqr_semitones": float(
            np.percentile(semis, 75) - np.percentile(semis, 25)
        ),
        "voiced_frac": float(np.mean(voiced)),
        "pauses": len(gaps),
        "mean_pause_s": float(np.mean(gaps)) if gaps else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: reel audit file.wav [file2.wav ...]", file=sys.stderr)
        return 2
    for path in argv:
        for key, val in audit(path).items():
            print(f"{key:20s} {val:.4f}" if isinstance(val, float) else f"{key:20s} {val}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
