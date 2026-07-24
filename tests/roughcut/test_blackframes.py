"""Black/dead-picture detection.

Regression guard for a real failure: a weekly call went black for 3.4 minutes
while people kept talking. Because the cut decision is transcript-driven, the
engine saw speech and kept it — 97s of black screen reached the rough cut.
"""
from __future__ import annotations
import subprocess

import pytest

from roughcut.blackframes import detect, total
from roughcut.decide import build_edl


def _clip(path, specs):
    """Build a clip by concatenating (lavfi_source, duration) segments."""
    ins, filt = [], ""
    for i, (src, dur) in enumerate(specs):
        # first option is joined with '=', later ones with ':'
        sep = ":" if "=" in src else "="
        ins += ["-f", "lavfi", "-i",
                f"{src}{sep}size=320x240:rate=25:duration={dur}"]
        filt += f"[{i}:v]"
    filt += f"concat=n={len(specs)}:v=1:a=0"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins,
                    "-filter_complex", filt, "-pix_fmt", "yuv420p", str(path)],
                   check=True)
    return str(path)


def test_detects_black_span_between_content(tmp_path):
    v = _clip(tmp_path / "a.mp4",
              [("testsrc", 3), ("color=black", 3), ("testsrc", 3)])
    r = detect(v)
    assert len(r) == 1
    start, end = r[0]
    assert start == pytest.approx(3.0, abs=0.3)
    assert end == pytest.approx(6.0, abs=0.3)
    assert total(r) == pytest.approx(3.0, abs=0.4)


def test_no_false_positives_on_normal_footage(tmp_path):
    v = _clip(tmp_path / "b.mp4", [("testsrc", 4)])
    assert detect(v) == []


def test_short_blips_ignored_below_min_dur(tmp_path):
    """A 0.2s flash must not fragment the timeline at the 0.4s default."""
    v = _clip(tmp_path / "c.mp4",
              [("testsrc", 2), ("color=black", 0.2), ("testsrc", 2)])
    assert detect(v) == []
    assert detect(v, min_dur=0.1) != []


def test_black_ranges_are_excluded_from_the_edl():
    """The payload: black time must not survive into kept ranges, even though
    the words spoken over it are perfectly good."""
    transcript = {
        "source": "/tmp/fake.mp4",
        "duration": 30.0,
        "words": [{"i": i, "start": float(i), "end": i + 0.9, "text": f"w{i}"}
                  for i in range(30)],
    }
    black = [[10.0, 20.0]]
    edl = build_edl(transcript, exclude_ranges=black)
    overlap = sum(max(0.0, min(e, 20.0) - max(s, 10.0))
                  for s, e in [(k["start"], k["end"]) for k in edl["keep"]])
    assert overlap == pytest.approx(0.0, abs=0.05)
    assert edl["keep"], "everything outside the black range should survive"
