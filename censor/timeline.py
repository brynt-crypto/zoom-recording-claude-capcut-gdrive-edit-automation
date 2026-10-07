"""Map censor windows (source seconds) onto the rough-cut timeline.

The rough-cut draft is the intro clip followed by the EDL keep segments laid end
to end, so a source window can be split by cuts (pauses and fillers removed
inside it) and lands as one or more timeline spans.
"""
from __future__ import annotations

_MERGE_GAP = 0.05          # spans closer than this are one span


def map_window(start: float, end: float, keep: list[dict],
               offset: float = 0.0) -> list[list[float]]:
    """Source window -> spans on the final timeline, ``offset`` seconds in."""
    spans, acc = [], 0.0
    for k in keep:
        lo, hi = max(start, k["start"]), min(end, k["end"])
        if hi > lo:
            spans.append([offset + acc + lo - k["start"],
                          offset + acc + hi - k["start"]])
        acc += k["end"] - k["start"]

    merged: list[list[float]] = []
    for s in spans:
        if merged and s[0] - merged[-1][1] < _MERGE_GAP:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return merged


def map_plan(plan: dict, edl: dict, intro_seconds: float = 0.0) -> dict:
    """Every blur and mute window mapped onto the final timeline."""
    keep = edl["keep"]
    out: dict = {"blur": [], "mute": []}
    for b in plan.get("blur") or []:
        for a, z in b["windows"]:
            out["blur"].append({"name": b["name"], "source": [a, z],
                                "cut": map_window(a, z, keep, intro_seconds)})
    for m in plan.get("mute") or []:
        a, z = m["window"]
        out["mute"].append({"name": m["name"], "source": [a, z],
                            "cut": map_window(a, z, keep, intro_seconds)})
    return out


def content_duration(edl: dict, intro_seconds: float = 0.0) -> float:
    """Intro + kept content, in seconds (the outro is appended after this)."""
    return intro_seconds + sum(k["end"] - k["start"] for k in edl["keep"])


def hms(t: float) -> str:
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}" if h else f"{int(m)}:{s:05.2f}"
