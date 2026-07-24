"""Detect silence ranges with ffmpeg silencedetect (a second signal alongside
transcript word-gaps). Returns a list of [start, end] silence intervals."""
from __future__ import annotations
import argparse
import json
import re
import subprocess

from . import config


def detect(wav_or_video: str, *, noise_db: float = config.SILENCE_NOISE_DB,
           min_dur: float = config.SILENCE_MIN_DUR) -> list[list[float]]:
    p = subprocess.run(
        ["ffmpeg", "-i", str(wav_or_video), "-af",
         f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    log = p.stderr  # silencedetect writes to stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", log)]
    ranges = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        ranges.append([round(s, 3), round(e, 3) if e is not None else None])
    return ranges


def main() -> None:
    ap = argparse.ArgumentParser(description="Detect silence ranges")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", default="silence.json")
    ap.add_argument("--noise-db", type=float, default=config.SILENCE_NOISE_DB)
    ap.add_argument("--min-dur", type=float, default=config.SILENCE_MIN_DUR)
    a = ap.parse_args()
    r = detect(a.input, noise_db=a.noise_db, min_dur=a.min_dur)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"silence": r}, f, indent=2)
    print(f"{len(r)} silence ranges -> {a.out}")


if __name__ == "__main__":
    main()
