"""Paths, layout, palette and guardrails for the CFE engine."""
from __future__ import annotations
import os

# Reuse roughcut's CapCut drafts root and outro so branding stays consistent.
from roughcut.build_draft import DEFAULT_DRAFTS_ROOT as DRAFTS_ROOT  # noqa: F401
from roughcut.config import INTRO_PATH, OUTRO_PATH, ASSETS_DIR  # noqa: F401

STYLE_REF_DIR = os.path.join(ASSETS_DIR, "style_ref")

# --- Palette (dark-tech / liquid-glass) -------------------------------------
ACCENT_HEX = "#22D3EE"      # electric cyan (override via --accent)
ACCENT_ALT_HEX = "#F5A623"  # warm alternate
GLASS_BASE_HEX = "#0B0F14"  # near-black glass base

# --- Layout: placement -> (transform_x, transform_y, scale) in half-canvas --
# transform_x: +right / -left; transform_y: +up / -down (1.0 == canvas edge).
LAYOUT = {
    # Subtitles and EVERY glass card share one consistent lower-third position
    # (ty) so captions and cards always appear at the same height. (tx, ty,
    # scale); ty negative = lower. Horizontal stays centered (a sideways offset
    # would clip a wide card).
    "lower_third":      (0.0, -0.55, 1.0),
    # All card treatments use one shared position AND one shared scale, so cards
    # never jump around in height or size between beats.
    "left_card":        (0.0, -0.55, 0.60),
    "right_card":       (0.0, -0.55, 0.60),
    "bottom_banner":    (0.0, -0.55, 0.60),
    "floating_label":   (0.0, -0.55, 0.60),
    # pseudo-split: speaker pushed left & shrunk; card fills the right.
    "pseudo_speaker":   (-0.40, 0.0, 0.66),
    "pseudo_card":      (0.42, 0.0, 1.0),
    # end-screen: speaker masked frame left; text card right.
    "end_speaker":      (-0.42, 0.0, 1.0),
    "end_card":         (0.40, 0.0, 1.0),
}

STYLE_GUARDRAILS = (
    "Use graphics sparingly; keep the speaker as the hero; place overlays in "
    "negative space and never over the face; prioritize readability over "
    "decoration; premium UI glass cards, not stickers; subtle shadow/blur/"
    "rounded corners; avoid hyperactive transitions; emphasize key ideas, not "
    "every sentence; clean subtitle rhythm; end with a composed final frame."
)
