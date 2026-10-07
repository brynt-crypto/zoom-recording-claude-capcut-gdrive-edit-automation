"""Load and validate a censor plan.

Schema (``jobs/<job>/censor_plan.json``)::

    {
      "note": "free text — what this recording is and why these boxes exist",
      "source": "assets/to_edit/<job>.mp4",        # optional, else --source
      "output": "assets/to_edit/<job>_censored.mp4",  # optional
      "crop":  {"x": 1102, "y": 0, "w": 2596, "h": 1460,
                "out_w": 1920, "out_h": 1080},
      "blur":  [{"name": "why this is hidden",
                 "box": [x, y, w, h],              # SOURCE pixels, pre-crop
                 "windows": [[start, end], ...]}], # SOURCE seconds
      "mute":  [{"name": "why", "window": [start, end]}],
      "not_blurred_by_user_choice": ["..."],       # optional, for the record
      "residual_risk": ["..."]                     # optional
    }

Times are seconds in the SOURCE recording, and blur boxes are source pixels
applied before the crop — so a plan stays valid whatever the delivery size.
"""
from __future__ import annotations
import json
from pathlib import Path

_CROP_KEYS = ("x", "y", "w", "h", "out_w", "out_h")


def load(path: str | Path) -> dict:
    """Read a plan and fail loudly if it cannot be acted on."""
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    errs = validate(plan)
    if errs:
        raise ValueError("invalid censor plan:\n  - " + "\n  - ".join(errs))
    return plan


def validate(plan: dict) -> list[str]:
    errs: list[str] = []
    crop = plan.get("crop")
    if not isinstance(crop, dict):
        errs.append("no 'crop' block")
    else:
        for k in _CROP_KEYS:
            if not isinstance(crop.get(k), int):
                errs.append(f"crop.{k} must be an int")

    if not plan.get("blur") and not plan.get("mute"):
        errs.append("plan censors nothing: both 'blur' and 'mute' are empty")

    for i, b in enumerate(plan.get("blur") or []):
        tag = f"blur[{i}]"
        box = b.get("box")
        if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, int) for v in box)):
            errs.append(f"{tag}.box must be [x, y, w, h] in source pixels")
        wins = b.get("windows")
        if not isinstance(wins, list) or not wins:
            errs.append(f"{tag}.windows is empty — a box with no window blurs nothing")
        else:
            errs += _window_errs(wins, tag)
        if not (b.get("name") or "").strip():
            errs.append(f"{tag}.name is empty — say what is being hidden")

    for i, m in enumerate(plan.get("mute") or []):
        tag = f"mute[{i}]"
        errs += _window_errs([m.get("window")], tag)
        if not (m.get("name") or "").strip():
            errs.append(f"{tag}.name is empty — say what is being silenced")
    return errs


def _window_errs(windows, tag: str) -> list[str]:
    errs = []
    for j, w in enumerate(windows):
        if not (isinstance(w, list) and len(w) == 2
                and all(isinstance(v, (int, float)) for v in w)):
            errs.append(f"{tag} window {j} must be [start, end] in seconds")
        elif w[1] <= w[0]:
            errs.append(f"{tag} window {j} ends at or before it starts")
    return errs


def counts(plan: dict) -> str:
    """One-line summary for logs."""
    blurs = plan.get("blur") or []
    wins = sum(len(b.get("windows") or []) for b in blurs)
    return (f"{len(blurs)} blur box(es) over {wins} window(s), "
            f"{len(plan.get('mute') or [])} mute window(s)")
