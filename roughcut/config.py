"""Tunable defaults for the rough-cut engine.

All time values are in SECONDS unless noted. Override per-run from the CLI/
pipeline. Defaults aim for a safe-but-tight talking-head rough cut.
"""
from __future__ import annotations

# --- Transcription -----------------------------------------------------------
WHISPER_MODEL = "medium"        # base | small | medium | large-v3 (bigger = slower, better)
WHISPER_DEVICE = "cpu"          # CLI default; the /roughcut command uses "cuda"
WHISPER_COMPUTE = "int8"        # int8 (cpu) | float16 (gpu)
LANGUAGE = None                 # None = auto-detect (handles Tagalog/English/Taglish)

# --- Silence / pause handling ------------------------------------------------
# Only remove dead air beyond this much — short natural pauses are kept as-is.
MIN_CUT = 0.20
# Silence left attached to a kept word after trimming a long dead-air gap.
KEEP_PAUSE = 0.20
# Comprehension pauses (after a sentence end or a question) are PRESERVED up to
# this length so the viewer can absorb the point; only trimmed beyond it.
SENTENCE_PAUSE = 0.80
# Characters that mark the end of a sentence / a question (pause worth keeping).
SENTENCE_END_CHARS = ".?!…。？！"
# ffmpeg silencedetect noise floor / min duration (used as a second signal).
SILENCE_NOISE_DB = -32.0
SILENCE_MIN_DUR = 0.35

# --- Black / dead-picture handling -------------------------------------------
# The cut decision is transcript-driven, so a blackout with talking over it would
# otherwise survive into the edit. Ranges at least BLACK_MIN_DUR seconds long are
# removed automatically. BLACK_PIX_TH is the per-pixel blackness threshold
# (0.0 = perfectly black); 0.10 tolerates compression noise in near-black frames.
BLACK_MIN_DUR = 0.4
BLACK_PIX_TH = 0.10

# --- Padding around kept speech ----------------------------------------------
# Expand each kept word boundary outward so we never clip the attack/release of
# a word. Whisper word edges are ~50-150ms loose, so keep these generous.
PAD_BEFORE = 0.12
PAD_AFTER = 0.20

# --- Segment merging (keeps CapCut timelines manageable) ---------------------
# Adjacent keep-ranges separated by a cut shorter than this are merged into one
# (the tiny cut is not worth a new segment; reduces draft size on long videos).
MERGE_GAP = 0.20

# --- Branding: intro / outro -------------------------------------------------
# Clips prepended/appended to every rough cut (drop your files here).
import os as _os
import glob as _glob
import sys as _sys
_BASE = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
ASSETS_DIR = _os.path.join(_BASE, "assets")
_VID_EXT = (".mp4", ".mov", ".mkv", ".m4v", ".webm")


def _resolve_branding(stem: str) -> str:
    """Find assets/<stem>.* case-insensitively (handles Intro.mp4 / .mov)."""
    for h in _glob.glob(_os.path.join(ASSETS_DIR, "*")):
        base, ext = _os.path.splitext(_os.path.basename(h))
        if base.lower() == stem and ext.lower() in _VID_EXT:
            return h
    return _os.path.join(ASSETS_DIR, f"{stem}.mp4")


INTRO_PATH = _resolve_branding("intro")
OUTRO_PATH = _resolve_branding("outro")
# Where /roughcut looks for source videos first (drop-folder), then falls back
# to scanning the user's main video locations. Override the fallback locations
# with the ROUGHCUT_SCAN_DIRS env var (os.pathsep-separated list of folders).
INBOX_DIR = _os.path.join(ASSETS_DIR, "to_edit")
if _sys.platform == "win32":
    SCAN_DIRS = [
        _os.path.expanduser(r"~\Videos"),
        _os.path.expanduser(r"~\Downloads"),
    ]
else:
    # macOS / Linux fallback scan locations.
    SCAN_DIRS = [
        _os.path.expanduser("~/Movies"),
        _os.path.expanduser("~/Downloads"),
    ]
_scan_override = _os.environ.get("ROUGHCUT_SCAN_DIRS", "").strip()
if _scan_override:
    SCAN_DIRS = [p for p in _scan_override.split(_os.pathsep) if p]

# --- Filler / stutter removal ------------------------------------------------
# Single-token fillers (normalized, punctuation stripped, lowercased).
FILLER_WORDS = {
    # English
    "um", "uh", "uhh", "umm", "erm", "er", "ah", "ahh", "eh", "hmm", "mm",
    "like", "basically", "literally", "actually", "right", "okay", "ok", "so",
    "you know", "i mean", "kind of", "sort of",
    # Taglish / Tagalog fillers
    "ano", "kasi", "diba", "di ba", "parang", "yung", "eto", "kaya",
}
# Phrase-level fillers (checked against a sliding window of normalized tokens).
FILLER_PHRASES = {"you know", "i mean", "kind of", "sort of", "di ba"}

# Immediate stutter: the same normalized token repeated back-to-back within
# this gap is collapsed to a single occurrence (keep the last, cut the earlier).
STUTTER_MAX_GAP = 0.60

# --- Output ------------------------------------------------------------------
# Re-encode preset for the preview render (quality/speed tradeoff).
PREVIEW_CRF = 20
PREVIEW_PRESET = "veryfast"
