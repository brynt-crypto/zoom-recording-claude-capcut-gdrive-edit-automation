# tests/finishing/test_build_intro.py
"""FIX 1 — verify the company intro is prepended to the CFE draft base track.

Creates a real 2s intro clip and a real 8s source clip via ffmpeg testsrc,
calls build() with intro_path, and asserts:
  - base track has len(keep)+1 = 2 segments (intro + one keep-range segment)
  - first segment occupies [0, intro_dur) on the final timeline
  - second segment starts at ~intro_dur on the final timeline
"""
import json
import subprocess
from pathlib import Path

import pytest

from finishing.build_finish import build


def _make_clip(path: Path, duration: float, size: str = "640x360") -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=30",
         "-t", str(duration), "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True,
    )
    return path


def test_intro_prepended_to_base_track(tmp_path):
    """Intro segment is first on base track; keep-range segment starts at intro_dur."""
    intro = _make_clip(tmp_path / "intro.mp4", 2.0)
    src = _make_clip(tmp_path / "clip.mp4", 8.0)

    edl = {"source": str(src), "fps": 30, "width": 640, "height": 360,
           "keep": [{"start": 0.0, "end": 8.0}]}
    manifest = {"job": "intro_test", "beats": []}

    path = build(
        edl, manifest, "demo_(CFE Edit)_v1",
        drafts_root=str(tmp_path / "drafts"),
        accent_hex="#22D3EE",
        intro_path=str(intro),
        do_end_screen=False,
    )

    data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
    base_track = next(t for t in data["tracks"] if t.get("name") == "base")
    segs = base_track["segments"]

    # Base track must have intro + 1 keep-range segment = len(keep) + 1 = 2
    assert len(segs) == len(edl["keep"]) + 1, (
        f"expected {len(edl['keep']) + 1} base segments (intro + keep ranges), "
        f"got {len(segs)}: {[s.get('target_timerange') for s in segs]}"
    )

    # First segment is the intro: starts at 0, duration ≈ intro_dur (2s).
    intro_seg = segs[0]
    intro_tr = intro_seg["target_timerange"]
    assert intro_tr["start"] == 0, (
        f"intro segment must start at t=0, got start={intro_tr['start']}"
    )
    # Duration within 50ms tolerance (ffprobe / VideoMaterial rounding).
    intro_dur_us = intro_tr["duration"]
    assert abs(intro_dur_us - 2_000_000) < 50_000, (
        f"intro segment duration should be ~2s (2_000_000µs), got {intro_dur_us}µs"
    )

    # Second segment (keep range) must start at intro_dur on the timeline.
    keep_seg = segs[1]
    keep_tr = keep_seg["target_timerange"]
    expected_start = intro_dur_us  # same value as what intro reported
    assert abs(keep_tr["start"] - expected_start) < 50_000, (
        f"keep-range segment should start at ~{expected_start}µs (intro_dur), "
        f"got start={keep_tr['start']}µs"
    )


def test_build_without_intro_unchanged(tmp_path):
    """Without intro_path, build() behaves as before: base segments == len(keep)."""
    src = _make_clip(tmp_path / "clip.mp4", 8.0)

    edl = {"source": str(src), "fps": 30, "width": 640, "height": 360,
           "keep": [{"start": 0.0, "end": 8.0}]}
    manifest = {"job": "no_intro_test", "beats": []}

    path = build(
        edl, manifest, "demo_(CFE Edit)_v1",
        drafts_root=str(tmp_path / "drafts"),
        accent_hex="#22D3EE",
        do_end_screen=False,
    )

    data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
    base_track = next(t for t in data["tracks"] if t.get("name") == "base")
    assert len(base_track["segments"]) == len(edl["keep"]), (
        "without intro, base segment count must equal number of keep ranges"
    )
    # First segment starts at t=0 when no intro.
    assert base_track["segments"][0]["target_timerange"]["start"] == 0


def test_intro_zoom_adds_keyframes_only_when_requested(tmp_path):
    """intro_zoom=True puts scale keyframes on the intro segment; default adds none."""
    intro = _make_clip(tmp_path / "intro.mp4", 2.0)
    src = _make_clip(tmp_path / "clip.mp4", 8.0)
    edl = {"source": str(src), "fps": 30, "width": 640, "height": 360,
           "keep": [{"start": 0.0, "end": 8.0}]}
    manifest = {"job": "iz", "beats": []}

    def _intro_keyframes(intro_zoom):
        path = build(edl, manifest, "demo_(CFE Edit)_v1",
                     drafts_root=str(tmp_path / ("dz" if intro_zoom else "dn")),
                     accent_hex="#22D3EE", intro_path=str(intro),
                     do_end_screen=False, intro_zoom=intro_zoom)
        data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
        base = next(t for t in data["tracks"] if t.get("name") == "base")
        return sum(len(k.get("keyframe_list", [])) for k in base["segments"][0].get("common_keyframes", []))

    assert _intro_keyframes(True) >= 3, "intro_zoom=True should keyframe the intro segment"
    assert _intro_keyframes(False) == 0, "default must leave the branded intro untouched"
