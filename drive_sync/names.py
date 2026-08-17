"""Derive a clean job slug from a Zoom recording filename.

Examples:
  "Ai Mastery Zoom Room2026-06-18T17 00 59Z.mp4" -> "ai_mastery_zoom_room_2026-06-18"
  "Impromptu Zoom Meeting - Jun 4 2026.mp4"      -> "impromptu_zoom_meeting_jun_4_2026"
"""
from __future__ import annotations
import os
import re

_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return re.sub(r"_+", "_", s)


def job_slug(filename: str) -> str:
    """Stable, filesystem-safe job name. Keeps an ISO date intact if present."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    m = _DATE.search(stem)
    if m:
        title = _slugify(stem[: m.start()])
        date = m.group(1)
        return f"{title}_{date}" if title else date
    return _slugify(stem) or "recording"
