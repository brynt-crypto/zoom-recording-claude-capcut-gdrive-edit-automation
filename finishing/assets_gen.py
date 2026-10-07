"""Media helpers: probe durations, sample style-ref frames, extract stills.

Card PNGs are rendered by ``finishing.cards``.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path


def probe_duration(path: str) -> float:
    """Return the media duration in seconds via ffprobe, or 0.0 if unavailable.

    Returns 0.0 when the path is missing, empty, or ffprobe fails so callers can
    safely treat a missing asset as zero-length without raising.
    """
    if not path or not Path(path).exists():
        return 0.0
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(probe.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def sample_style_ref(style_ref_dir: str, out_dir: str, per_video: int = 3) -> list[str]:
    # Guard: nonexistent input dir must not create the output dir as a side effect.
    if not os.path.isdir(style_ref_dir):
        return []
    os.makedirs(out_dir, exist_ok=True)
    frames: list[str] = []
    vids = [p for p in Path(style_ref_dir).iterdir()
            if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")]
    for vid in vids:
        # Probe duration so we can compute absolute timestamps (ffmpeg -ss does
        # not accept percentage strings).
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(vid)],
            capture_output=True, text=True)
        try:
            duration = float(probe.stdout.strip())
        except (ValueError, AttributeError):
            continue  # Skip videos whose duration cannot be determined.
        for n in range(per_video):
            # Evenly spaced timestamps, skipping the very start and end.
            ts = duration * (n + 1) / (per_video + 1)
            out = os.path.join(out_dir, f"{vid.stem}_{n}.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", str(vid),
                 "-frames:v", "1", "-q:v", "3", out],
                check=False, capture_output=True)
            if os.path.exists(out):
                frames.append(out)
    return frames


def extract_frame(video_path: str, out_png: str, at_seconds: float) -> str | None:
    """Grab a single frame from video_path at ~at_seconds as a PNG (a freeze
    frame). Returns the path, or None if ffmpeg failed. Uses -ss before -i for
    a fast, accurate-enough seek."""
    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{max(0.0, at_seconds):.3f}", "-i", video_path,
         "-frames:v", "1", "-q:v", "2", out_png],
        check=False, capture_output=True)
    return out_png if os.path.exists(out_png) else None
