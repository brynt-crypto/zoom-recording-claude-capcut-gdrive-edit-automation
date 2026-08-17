"""Load + validate the Claude-authored storyboard manifest.

storyboard.json schema (see animate/prompts/03_storyboard.md):
{
  "job": str,
  "style": str,                     # global style note woven into every prompt
  "scenes": [
    { "id": int,
      "start": float, "end": float, # narration seconds; contiguous from 0.0
      "spoken": str,                # the narration line (context only)
      "caption": str,               # short on-screen label; "" = no caption
      "image_prompt": str,          # required, non-empty
      "negative_prompt": str,       # optional
      "motion": str,                # one of animate.motion.MOTIONS
      "emphasis": bool }            # optional; stronger zoom + bolder caption
  ]
}
"""
from __future__ import annotations
import json
from pathlib import Path

from . import config
from .motion import MOTIONS

# Contiguity tolerance (seconds) — whisper boundaries are a little loose.
_TOL = 0.06


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(manifest: dict, narration_dur: float) -> list[str]:
    """Return a list of human-readable errors (empty == valid)."""
    errs: list[str] = []
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return ["storyboard has no scenes"]

    prev_end = 0.0
    for idx, s in enumerate(scenes):
        tag = f"scene {s.get('id', idx + 1)}"
        try:
            start = float(s["start"])
            end = float(s["end"])
        except (KeyError, TypeError, ValueError):
            errs.append(f"{tag}: missing/invalid start or end")
            continue

        if idx == 0 and abs(start) > _TOL:
            errs.append(f"{tag}: first scene must start at 0.0 (got {start})")
        if end <= start:
            errs.append(f"{tag}: end ({end}) must be > start ({start})")
        elif (end - start) < config.SCENE_MIN_SEC - _TOL:
            errs.append(f"{tag}: too short ({end - start:.2f}s < {config.SCENE_MIN_SEC}s)")
        if abs(start - prev_end) > _TOL:
            errs.append(f"{tag}: not contiguous — starts at {start}, previous ended {prev_end:.2f}")
        if end > narration_dur + _TOL:
            errs.append(f"{tag}: end ({end}) exceeds narration duration ({narration_dur:.2f})")
        prev_end = end

        motion = s.get("motion", "static")
        if motion not in MOTIONS:
            errs.append(f"{tag}: unknown motion {motion!r} (allowed: {sorted(MOTIONS)})")
        if not (s.get("image_prompt") or "").strip():
            errs.append(f"{tag}: empty image_prompt")

    # Warn (not fail) if the storyboard leaves a big tail of narration uncovered.
    if scenes and narration_dur - prev_end > config.SCENE_MAX_SEC:
        errs.append(
            f"scenes cover only {prev_end:.1f}s of {narration_dur:.1f}s narration — "
            f"add scenes so the last one ends near {narration_dur:.1f}s")
    return errs
