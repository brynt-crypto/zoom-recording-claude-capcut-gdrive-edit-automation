"""Load, validate and normalize the Claude-authored finishing manifest."""
from __future__ import annotations
import json

TREATMENTS = frozenset({
    "subtitle_only", "subtitle+punch_in", "left_card", "right_card",
    "bottom_banner", "floating_label", "pseudo_split", "end_screen",
})
PLACEMENTS = frozenset({
    "lower_third", "left_card", "right_card", "bottom_banner",
    "floating_label", "center",
})
_REQUIRED = ("id", "type", "treatment", "final_in", "final_out")


def load_manifest(path: str) -> dict:
    # utf-8-sig tolerates a UTF-8 BOM (some editors / PowerShell Out-File add one).
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def validate(manifest: dict, final_duration: float) -> list[str]:
    errs: list[str] = []
    beats = manifest.get("beats")
    if not isinstance(beats, list) or not beats:
        return ["manifest has no beats"]
    for b in beats:
        tag = f"beat {b.get('id', '?')}"
        for k in _REQUIRED:
            if k not in b:
                errs.append(f"{tag}: missing required field '{k}'")
        if "treatment" in b and b["treatment"] not in TREATMENTS:
            errs.append(f"{tag}: invalid treatment '{b.get('treatment')}'")
        fi, fo = b.get("final_in"), b.get("final_out")
        if isinstance(fi, (int, float)) and isinstance(fo, (int, float)):
            if fo <= fi:
                errs.append(f"{tag}: inverted/zero range ({fi} -> {fo})")
            if fi < 0 or fo > final_duration + 0.05:
                errs.append(f"{tag}: out of bounds (0..{final_duration})")
    return errs


def normalize(manifest: dict) -> dict:
    out = dict(manifest)
    beats = out.get("beats", [])
    processed_beats = []
    for b in beats:
        nb = dict(b)
        nb.setdefault("glass", True)
        nb.setdefault("punch_in", None)
        nb.setdefault("subtitle_emphasis", False)
        nb.setdefault("reposition_overlays", False)
        nb.setdefault("accent", None)
        nb.setdefault("anim_in", "fade")
        nb.setdefault("anim_out", "fade")
        nb.setdefault("text", "")
        nb.setdefault("placement", "lower_third")
        processed_beats.append(nb)
    processed_beats.sort(key=lambda x: x["final_in"])
    out["beats"] = processed_beats
    return out
