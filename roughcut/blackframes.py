"""Detect black (dead-picture) ranges with ffmpeg blackdetect.

Why this exists: the rough cut decides what to keep from the TRANSCRIPT, so it
only ever sees speech. If the recording's picture goes black while someone keeps
talking — a dropped screen share, a camera cut, a Zoom hiccup — the engine has no
reason to remove it and the blackout survives into the edit. (Seen live: a 3.4
minute blackout in a weekly call, 97s of which reached the rough cut.)

The ranges returned here are fed to `build_edl(exclude_ranges=...)`, reusing the
same machinery as a manual `--exclude`, so black picture is cut even when the
audio is perfectly good.

Returns a list of [start, end] intervals in SOURCE seconds.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess

from . import config


def detect(video: str, *, min_dur: float = config.BLACK_MIN_DUR,
           pix_th: float = config.BLACK_PIX_TH) -> list[list[float]]:
    """Scan `video` for black stretches at least `min_dur` seconds long.

    `pix_th` is the per-pixel blackness threshold (0.0 = perfectly black); 0.10
    tolerates the slight noise of a compressed near-black frame.
    """
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
         f"blackdetect=d={min_dur}:pix_th={pix_th}", "-an", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    log = p.stderr  # blackdetect writes to stderr
    ranges = []
    for m in re.finditer(r"black_start:([\d.]+)\s+black_end:([\d.]+)", log):
        start, end = float(m.group(1)), float(m.group(2))
        if end > start:
            ranges.append([round(start, 3), round(end, 3)])
    return ranges


def total(ranges) -> float:
    return round(sum(e - s for s, e in ranges), 2)


def main() -> None:
    ap = argparse.ArgumentParser(description="Detect black-frame ranges")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", default="blackframes.json")
    ap.add_argument("--min-dur", type=float, default=config.BLACK_MIN_DUR)
    ap.add_argument("--pix-th", type=float, default=config.BLACK_PIX_TH)
    a = ap.parse_args()
    r = detect(a.input, min_dur=a.min_dur, pix_th=a.pix_th)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"black": r}, f, indent=2)
    print(f"{len(r)} black ranges ({total(r)}s) -> {a.out}")
    for s, e in r:
        print(f"   {s:9.2f} - {e:9.2f}  ({e - s:.2f}s)")


if __name__ == "__main__":
    main()
