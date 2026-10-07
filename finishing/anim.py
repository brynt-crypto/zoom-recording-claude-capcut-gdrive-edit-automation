"""Animation vocabulary — tiered, so the manifest picks deliberately.

The CapCut library exposes 249 image intros / 216 outros / 182 text intros /
81 text loops. Exposing all of them invites spectacle, so these are curated into
three tiers and gives every treatment a sensible DEFAULT. A beat only names an
animation when it wants something other than its default, and anything in the
BOLD tier must carry a justification (enforced in beats.validate).

Names here are stable English keys; the CapCut enum members (Chinese) are an
implementation detail that never reaches the manifest.
"""
from __future__ import annotations

SUBTLE, STANDARD, BOLD = "subtle", "standard", "bold"

# key -> (tier, pycapcut IntroType member, duration)
IMAGE_IN = {
    "fade":        (SUBTLE,   "渐显",       "0.4s"),
    "soft_zoom":   (SUBTLE,   "轻微放大",   "0.5s"),
    "blur_fade":   (SUBTLE,   "模糊渐显",   "0.5s"),
    "slide_up":    (SUBTLE,   "向上滑动",   "0.4s"),
    "slide_right": (STANDARD, "向右滑动",   "0.4s"),
    "slide_left":  (STANDARD, "向左滑动",   "0.4s"),
    "zoom":        (STANDARD, "放大",       "0.4s"),
    "wipe":        (STANDARD, "画面擦除",   "0.5s"),
    "punch_zoom":  (STANDARD, "动感放大",   "0.4s"),
    "shake":       (BOLD,     "轻微抖动",   "0.4s"),
    "tv_on":       (BOLD,     "TV开启",     "0.6s"),
    "noise":       (BOLD,     "噪点渐显",   "0.5s"),
}

# key -> (tier, pycapcut OutroType member, duration)
IMAGE_OUT = {
    "fade":      (SUBTLE,   "渐隐",     "0.4s"),
    "blur_fade": (SUBTLE,   "模糊渐隐", "0.5s"),
    "shrink":    (STANDARD, "缩小",     "0.4s"),
    "wipe":      (STANDARD, "画面擦除", "0.5s"),
    "noise":     (BOLD,     "噪点渐隐", "0.5s"),
}

# key -> (tier, pycapcut TextIntro member, duration)
TEXT_IN = {
    "fade":       (SUBTLE,   "渐显",       "0.4s"),
    "typewriter": (SUBTLE,   "打字机",     "0.9s"),
    "per_word":   (SUBTLE,   "逐字",       "0.8s"),
    "reveal":     (SUBTLE,   "逐字显影",   "0.8s"),
    "rise":       (STANDARD, "向上弹入",   "0.5s"),
    "wipe_right": (STANDARD, "向右擦除",   "0.5s"),
    "pop":        (STANDARD, "弹入",       "0.4s"),
    "dissolve":   (STANDARD, "溶解_入场", "0.5s"),
    "countdown":  (BOLD,     "倒数",       "1.0s"),
    "glitch_type":(BOLD,     "故障打字机", "0.9s"),
}

# key -> (tier, pycapcut TextOutro member, duration)
TEXT_OUT = {
    "fade":       (SUBTLE,   "渐隐",     "0.4s"),
    "wipe_up":    (STANDARD, "向上擦除", "0.4s"),
    "dissolve_up":(STANDARD, "向上溶解", "0.4s"),
}

# key -> (tier, pycapcut TextLoopAnim member)
TEXT_LOOP = {
    "pulse":  (STANDARD, "脉冲闪动"),
    "glow":   (STANDARD, "漂浮发光"),
    "blur":   (STANDARD, "发光模糊"),
    "blink":  (BOLD,     "闪烁"),
}

# Default animation per treatment. Anything not listed falls back to fade/fade.
DEFAULTS = {
    "subtitle_only":     ("fade", "fade"),
    "subtitle+punch_in": ("fade", "fade"),
    "left_card":         ("slide_up", "fade"),
    "right_card":        ("slide_up", "fade"),
    "bottom_banner":     ("slide_up", "fade"),
    "floating_label":    ("soft_zoom", "fade"),
    "pseudo_split":      ("slide_right", "fade"),
    "process_flow":      ("slide_right", "fade"),
    "checklist":         ("slide_up", "fade"),
    "timeline":          ("slide_up", "fade"),
    "comparison":        ("wipe", "fade"),
    "stat_counter":      ("punch_zoom", "fade"),
    "bar_chart":         ("wipe", "fade"),
    "quote":             ("blur_fade", "fade"),
    "lower_third":       ("slide_right", "fade"),
    "cta":               ("zoom", "fade"),
    "end_screen":        ("fade", "fade"),
}

# How many BOLD-tier animations one video may use before validation complains.
BOLD_BUDGET = 4


def tier_of(table: dict, key: str) -> str | None:
    row = table.get(key)
    return row[0] if row else None


def resolve(p, table: dict, key: str, enum_name: str):
    """Return (pycapcut enum member, duration) for a vocabulary key.

    Falls back to the table's "fade" entry when the key is unknown, so an
    unexpected value degrades to v1 behaviour instead of raising mid-build.
    """
    row = table.get(key) or table.get("fade")
    enum = getattr(p, enum_name)
    member = getattr(enum, row[1], None)
    if member is None:                      # library drift — degrade safely
        row = table["fade"]
        member = getattr(enum, row[1])
    dur = row[2] if len(row) > 2 else None
    return member, dur


def bold_keys_used(beats: list[dict]) -> list[tuple]:
    """List (beat_id, field, key) for every BOLD-tier animation in the manifest."""
    used = []
    for b in beats:
        for field, table in (("anim_in", IMAGE_IN), ("anim_out", IMAGE_OUT),
                             ("text_anim_in", TEXT_IN), ("text_anim_out", TEXT_OUT),
                             ("text_loop", TEXT_LOOP)):
            key = b.get(field)
            if key and tier_of(table, key) == BOLD:
                used.append((b.get("id"), field, key))
        for layer in b.get("layers") or []:
            key = layer.get("anim_in")
            if key and tier_of(IMAGE_IN, key) == BOLD:
                used.append((b.get("id"), "layer.anim_in", key))
    return used
