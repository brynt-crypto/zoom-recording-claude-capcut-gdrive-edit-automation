"""CFE Standard manifest schema.

On top of the eight core treatments it adds:
  * motion-graphic treatments from the beginner motion-graphics catalogue
    (process_flow, checklist, timeline, comparison, bar_chart, quote,
    stat_counter, lower_third, cta),
  * a named animation vocabulary (see anim) instead of a single fade,
  * multi-layer beats, so elements stagger in rather than appearing at once.

Manifests written for the older engine stay valid: every added field is
optional and every core treatment still validates.
"""
from __future__ import annotations
import json

from common.env import env_list
from . import anim

CORE_TREATMENTS = frozenset({
    "subtitle_only", "subtitle+punch_in", "left_card", "right_card",
    "bottom_banner", "floating_label", "pseudo_split", "end_screen",
})
GRAPHIC_TREATMENTS = frozenset({
    "process_flow", "checklist", "timeline", "comparison", "bar_chart",
    "quote", "stat_counter", "lower_third", "cta",
})
TREATMENTS = CORE_TREATMENTS | GRAPHIC_TREATMENTS

# Treatments rendered as a card PNG on the overlay track.
CARD_TREATMENTS = frozenset({
    "left_card", "right_card", "bottom_banner", "floating_label",
    "pseudo_split", "end_screen",
}) | GRAPHIC_TREATMENTS

# Treatments whose `layers` list drives a staggered reveal.
LAYERED_TREATMENTS = frozenset({"process_flow", "checklist", "timeline"})

_REQUIRED = ("id", "type", "treatment", "final_in", "final_out")

# Only the host may be named in a lower third. Members stay anonymous, matching
# the transcript redactor's posture (the host stays visible, everyone else is
# redacted). Set HOST_NAMES in .env, e.g. HOST_NAMES=Jordan,Jo — when it is unset
# no on-screen name is allowed at all.
LOWER_THIRD_ALLOWED_NAMES = env_list("HOST_NAMES")


def load_manifest(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def validate(manifest: dict, final_duration: float) -> list[str]:
    errs: list[str] = []
    beats = manifest.get("beats")
    if not isinstance(beats, list) or not beats:
        return ["manifest has no beats"]

    seen_ids = set()
    for b in beats:
        tag = f"beat {b.get('id', '?')}"
        for k in _REQUIRED:
            if k not in b:
                errs.append(f"{tag}: missing required field '{k}'")

        bid = b.get("id")
        if bid in seen_ids:
            errs.append(f"{tag}: duplicate id")
        seen_ids.add(bid)

        tr = b.get("treatment")
        if tr and tr not in TREATMENTS:
            errs.append(f"{tag}: invalid treatment '{tr}'")

        fi, fo = b.get("final_in"), b.get("final_out")
        if isinstance(fi, (int, float)) and isinstance(fo, (int, float)):
            if fo <= fi:
                errs.append(f"{tag}: inverted/zero range ({fi} -> {fo})")
            if fi < 0 or fo > final_duration + 0.05:
                errs.append(f"{tag}: out of bounds (0..{final_duration})")

        # Animation keys must exist in the vocabulary.
        for field, table in (("anim_in", anim.IMAGE_IN),
                             ("anim_out", anim.IMAGE_OUT),
                             ("text_anim_in", anim.TEXT_IN),
                             ("text_anim_out", anim.TEXT_OUT),
                             ("text_loop", anim.TEXT_LOOP)):
            key = b.get(field)
            if key and key not in table:
                errs.append(f"{tag}: unknown {field} '{key}'")

        # Layered treatments need layers; layers only make sense there.
        layers = b.get("layers")
        if tr in LAYERED_TREATMENTS and not layers:
            errs.append(f"{tag}: treatment '{tr}' requires a non-empty 'layers' list")
        if layers:
            if not isinstance(layers, list):
                errs.append(f"{tag}: 'layers' must be a list")
            else:
                for j, layer in enumerate(layers):
                    if not layer.get("text"):
                        errs.append(f"{tag}: layer {j} has no text")
                    off = layer.get("offset", 0.0)
                    if not isinstance(off, (int, float)) or off < 0:
                        errs.append(f"{tag}: layer {j} has invalid offset {off!r}")
                    elif isinstance(fi, (int, float)) and isinstance(fo, (int, float)) \
                            and fi + off >= fo:
                        errs.append(
                            f"{tag}: layer {j} offset {off} starts at/after the beat ends")
                    key = layer.get("anim_in")
                    if key and key not in anim.IMAGE_IN:
                        errs.append(f"{tag}: layer {j} unknown anim_in '{key}'")

        # A named lower third may only name the host.
        if tr == "lower_third":
            name = (b.get("text") or "").strip()
            first = name.split("\n")[0].strip()
            if first and not any(first.lower().startswith(a.lower())
                                 for a in LOWER_THIRD_ALLOWED_NAMES):
                allowed = "/".join(LOWER_THIRD_ALLOWED_NAMES) or "set HOST_NAMES in .env"
                errs.append(
                    f"{tag}: lower_third names '{first}' — only the host "
                    f"({allowed}) may be named on screen")

        # BOLD-tier animations must say why.
        for field, table in (("anim_in", anim.IMAGE_IN),
                             ("anim_out", anim.IMAGE_OUT),
                             ("text_anim_in", anim.TEXT_IN),
                             ("text_loop", anim.TEXT_LOOP)):
            key = b.get(field)
            if key and anim.tier_of(table, key) == anim.BOLD \
                    and not (b.get("bold_reason") or "").strip():
                errs.append(f"{tag}: '{key}' is a BOLD animation and needs 'bold_reason'")

    bold = anim.bold_keys_used(beats)
    if len(bold) > anim.BOLD_BUDGET:
        errs.append(
            f"manifest uses {len(bold)} BOLD animations, budget is "
            f"{anim.BOLD_BUDGET} — soften all but the strongest moments")
    return errs


def normalize(manifest: dict) -> dict:
    out = dict(manifest)
    beats = []
    for b in out.get("beats", []):
        nb = dict(b)
        tr = nb.get("treatment", "")
        d_in, d_out = anim.DEFAULTS.get(tr, ("fade", "fade"))
        nb.setdefault("glass", True)
        nb.setdefault("punch_in", None)
        nb.setdefault("subtitle_emphasis", False)
        nb.setdefault("reposition_overlays", tr == "bottom_banner")
        nb.setdefault("accent", None)
        nb.setdefault("anim_in", d_in)
        nb.setdefault("anim_out", d_out)
        nb.setdefault("text", "")
        nb.setdefault("subtitle", "")
        nb.setdefault("placement", "lower_third")
        nb.setdefault("layers", [])
        nb.setdefault("bold_reason", "")
        # v1 wrote anim_in="fade" explicitly; keep that meaning identical.
        beats.append(nb)
    beats.sort(key=lambda x: x["final_in"])
    out["beats"] = beats
    return out
