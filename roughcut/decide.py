"""Turn a word-level transcript into an Edit Decision List (keep ranges + cuts).

This is the deterministic baseline: it removes long pauses, filler words, and
immediate stutters/word-repeats. The *semantic* layer (false starts, choosing
the best of repeated takes) is added on top by Claude in the /roughcut command,
which passes `extra_cut_indices` (word indices to also drop).

edl.json schema:
{
  "source","duration","fps","language",
  "keep": [{"start","end"}],
  "cuts": [{"start","end","reason","text"}],
  "stats": {...}, "params": {...}
}
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from . import config
from .util import hms

_PUNCT = re.compile(r"[^\w']", re.UNICODE)


def norm(text: str) -> str:
    return _PUNCT.sub("", text.strip().lower())


def ends_sentence(text: str, chars: str = config.SENTENCE_END_CHARS) -> bool:
    """True if a word ends a sentence/question — the pause after it is worth
    keeping so the viewer can absorb the point."""
    t = text.strip()
    return bool(t) and t[-1] in chars


def _mark_cuts(words: list[dict], *, filler_words, filler_phrases,
               stutter_gap: float, extra: set[int]) -> dict[int, str]:
    """Return {word_index: reason} for words to drop."""
    cut: dict[int, str] = {}
    normd = [norm(w["text"]) for w in words]

    for i, w in enumerate(words):
        if i in extra:
            cut[i] = "semantic"          # Claude-flagged (false start / repeated take)
        elif normd[i] in filler_words:
            cut[i] = "filler"

    # Phrase fillers (2-word sliding window).
    for i in range(len(words) - 1):
        pair = f"{normd[i]} {normd[i+1]}"
        if pair in filler_phrases:
            cut.setdefault(i, "filler")
            cut.setdefault(i + 1, "filler")

    # Immediate stutters: same token back-to-back within stutter_gap -> keep last.
    for i in range(1, len(words)):
        if not normd[i] or normd[i] != normd[i - 1]:
            continue
        if words[i]["start"] - words[i - 1]["end"] <= stutter_gap:
            cut.setdefault(i - 1, "stutter")
    return cut


def _subtract(window: list[float], excludes: list[list[float]]) -> list[list[float]]:
    """Return `window` with each exclude interval removed."""
    res = [list(window)]
    for ex in sorted(excludes):
        nxt = []
        for seg in res:
            if ex[1] <= seg[0] or ex[0] >= seg[1]:
                nxt.append(seg)
            else:
                if ex[0] > seg[0]:
                    nxt.append([seg[0], ex[0]])
                if ex[1] < seg[1]:
                    nxt.append([ex[1], seg[1]])
        res = nxt
    return res


def _intersect(keep: list[list[float]], allowed: list[list[float]]) -> list[list[float]]:
    out = []
    for k in keep:
        for a in allowed:
            s, e = max(k[0], a[0]), min(k[1], a[1])
            if e - s > 0.02:
                out.append([s, e])
    return sorted(out)


def apply_output_trims(edl: dict, out_trims: list[list[float]]) -> dict:
    """Remove ranges measured on the ASSEMBLED rough-cut timeline (what the user
    sees in CapCut), not the source. Maps each surviving output sub-range back to
    source coordinates and returns a new EDL.
    """
    trims = sorted([sorted(t) for t in out_trims])
    survivors: list[list[float]] = []
    o = 0.0
    for k in edl["keep"]:
        s, e = k["start"], k["end"]
        dur = e - s
        for so, eo in _subtract([o, o + dur], trims):
            if eo - so > 0.02:
                survivors.append([s + (so - o), s + (eo - o)])
        o += dur

    duration = float(edl["duration"])
    kept = sum(b - a for a, b in survivors)
    new = dict(edl)
    new["keep"] = [{"start": round(a, 3), "end": round(b, 3)} for a, b in survivors]
    new["output_trims"] = trims
    new["stats"] = dict(edl["stats"])
    new["stats"].update({
        "kept_sec": round(kept, 2),
        "removed_sec": round(duration - kept, 2),
        "removed_pct": round(100 * (duration - kept) / duration, 1) if duration else 0,
        "segments": len(survivors),
        "output_trim_sec": round(sum(b - a for a, b in trims), 2),
    })
    return new


def build_edl(transcript: dict, *,
              min_cut: float = config.MIN_CUT,
              keep_pause: float = config.KEEP_PAUSE,
              sentence_pause: float = config.SENTENCE_PAUSE,
              pad_before: float = config.PAD_BEFORE,
              pad_after: float = config.PAD_AFTER,
              merge_gap: float = config.MERGE_GAP,
              stutter_gap: float = config.STUTTER_MAX_GAP,
              filler_words=None, filler_phrases=None,
              extra_cut_indices=None,
              clip_start: float = 0.0,
              clip_end: float | None = None,
              exclude_ranges=None) -> dict:
    words = transcript["words"]
    duration = float(transcript["duration"])
    clip_end = duration if clip_end is None else min(clip_end, duration)
    clip_start = max(0.0, clip_start)
    exclude_ranges = [sorted(r) for r in (exclude_ranges or [])]
    filler_words = filler_words if filler_words is not None else config.FILLER_WORDS
    filler_phrases = filler_phrases if filler_phrases is not None else config.FILLER_PHRASES
    extra = set(extra_cut_indices or [])

    cut_reason = _mark_cuts(words, filler_words=filler_words,
                            filler_phrases=filler_phrases,
                            stutter_gap=stutter_gap, extra=extra)
    kept = [w for w in words if w["i"] not in cut_reason]

    # Build keep ranges from kept words. For each inter-word silence, keep a
    # buffer (so words never clip) and only remove dead air beyond it. A pause
    # after a sentence end / question is preserved up to `sentence_pause`.
    keep: list[list[float]] = []
    if kept:
        prev = kept[0]
        cur = [max(0.0, prev["start"] - pad_before), prev["end"]]
        for w in kept[1:]:
            gap = w["start"] - prev["end"]
            allowed = sentence_pause if ends_sentence(prev["text"]) else keep_pause
            # Removable dead air = gap minus the buffer we always leave on both
            # sides (pad_after after prev, pad_before before next) minus the
            # comprehension allowance.
            removable = gap - allowed - pad_before
            if removable > min_cut:
                # Trim: close current segment leaving `allowed` of silence after
                # prev word; reopen `pad_before` before the next word.
                cur[1] = prev["end"] + max(pad_after, allowed)
                keep.append(cur)
                cur = [max(cur[1], w["start"] - pad_before), w["end"]]
            else:
                # Short or wanted pause: keep continuous through to this word.
                cur[1] = w["end"]
            prev = w
        cur[1] = min(prev["end"] + pad_after, duration)
        keep.append(cur)

    # Merge ranges separated by a cut shorter than merge_gap (reduces segments).
    merged: list[list[float]] = []
    for r in keep:
        if merged and r[0] - merged[-1][1] < merge_gap:
            merged[-1][1] = r[1]
        else:
            merged.append([min(r[0], duration), min(r[1], duration)])
    merged = [r for r in merged if r[1] - r[0] > 0.02]

    # Apply manual head/tail trim + mid-range removals: keep only what's inside
    # [clip_start, clip_end] minus the exclude ranges.
    if clip_start > 0 or clip_end < duration or exclude_ranges:
        allowed = _subtract([clip_start, clip_end], exclude_ranges)
        merged = _intersect(merged, allowed)

    # Cuts = complement of keep within [0, duration]; label by dominant reason.
    cuts = []
    prev_end = 0.0
    for r in merged:
        if r[0] - prev_end > 0.02:
            cuts.append(_label_cut(prev_end, r[0], words, cut_reason,
                                   clip_start, clip_end, exclude_ranges))
        prev_end = r[1]
    if duration - prev_end > 0.02:
        cuts.append(_label_cut(prev_end, duration, words, cut_reason,
                               clip_start, clip_end, exclude_ranges))

    kept_dur = sum(r[1] - r[0] for r in merged)
    removed = duration - kept_dur
    reason_counts: dict[str, int] = {}
    for c in cuts:
        reason_counts[c["reason"]] = reason_counts.get(c["reason"], 0) + 1

    return {
        "source": transcript["source"],
        "duration": round(duration, 3),
        "fps": transcript.get("fps", 30.0),
        "width": transcript.get("width", 0),
        "height": transcript.get("height", 0),
        "language": transcript.get("language"),
        "keep": [{"start": round(a, 3), "end": round(b, 3)} for a, b in merged],
        "cuts": cuts,
        "stats": {
            "original_sec": round(duration, 2),
            "kept_sec": round(kept_dur, 2),
            "removed_sec": round(removed, 2),
            "removed_pct": round(100 * removed / duration, 1) if duration else 0,
            "segments": len(merged),
            "num_cuts": len(cuts),
            "cuts_by_reason": reason_counts,
            "words_total": len(words),
            "words_cut": len(cut_reason),
        },
        "params": {
            "min_cut": min_cut, "keep_pause": keep_pause,
            "sentence_pause": sentence_pause, "pad_before": pad_before,
            "pad_after": pad_after, "merge_gap": merge_gap,
            "stutter_gap": stutter_gap,
        },
    }


def _label_cut(start: float, end: float, words, cut_reason,
               clip_start: float = 0.0, clip_end: float | None = None,
               exclude_ranges=None) -> dict:
    mid = (start + end) / 2
    # Manual trims take priority in labelling (use midpoint so boundary-
    # straddling cuts are labelled by where their bulk lies).
    if mid <= clip_start:
        return {"start": round(start, 3), "end": round(end, 3),
                "reason": "trim-head", "text": ""}
    if clip_end is not None and mid >= clip_end:
        return {"start": round(start, 3), "end": round(end, 3),
                "reason": "trim-tail", "text": ""}
    for ex in (exclude_ranges or []):
        if mid >= ex[0] - 0.05 and mid <= ex[1] + 0.05:
            return {"start": round(start, 3), "end": round(end, 3),
                    "reason": "manual", "text": ""}
    inside = [w for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.05]
    reasons = {cut_reason.get(w["i"]) for w in inside if w["i"] in cut_reason}
    if not inside:
        reason = "pause"
    elif reasons == {"filler"}:
        reason = "filler"
    elif "semantic" in reasons:
        reason = "semantic"
    elif "stutter" in reasons:
        reason = "stutter"
    elif reasons:
        reason = "filler"
    else:
        reason = "pause"
    text = " ".join(w["text"] for w in inside)
    return {"start": round(start, 3), "end": round(end, 3),
            "reason": reason, "text": text}


def write_report(edl: dict, transcript: dict, out_md: str) -> None:
    s = edl["stats"]
    cut_spans = edl["cuts"]
    lines = [
        f"# Rough-cut review — {Path(edl['source']).name}",
        "",
        f"- Original: **{hms(s['original_sec'])}**  →  Rough cut: **{hms(s['kept_sec'])}**",
        f"- Removed: **{hms(s['removed_sec'])}** ({s['removed_pct']}%)  "
        f"across **{s['num_cuts']}** cuts → **{s['segments']}** keep-segments",
        f"- Cuts by reason: {s['cuts_by_reason']}",
        f"- Language: {edl.get('language')}",
        "",
        "## Transcript (struck-through = removed)",
        "",
    ]
    # Reconstruct: walk words; mark a word struck if it falls inside any cut span.
    def in_cut(w):
        for c in cut_spans:
            if w["start"] >= c["start"] - 0.05 and w["end"] <= c["end"] + 0.05:
                return c["reason"]
        return None

    buf, last_struck = [], None
    for w in transcript["words"]:
        r = in_cut(w)
        if r:
            buf.append(f"~~{w['text']}~~")
            last_struck = r
        else:
            buf.append(w["text"])
    lines.append(" ".join(buf))
    lines += ["", "## Cut list", ""]
    for c in cut_spans:
        dur = c["end"] - c["start"]
        preview = (c["text"][:60] + "…") if len(c["text"]) > 60 else c["text"]
        lines.append(f"- `{hms(c['start'])}–{hms(c['end'])}` "
                     f"({dur:.1f}s, {c['reason']})"
                     + (f": “{preview}”" if preview else ""))
    Path(out_md).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build EDL from transcript")
    ap.add_argument("transcript")
    ap.add_argument("-o", "--out", default="edl.json")
    ap.add_argument("--report", default="cuts_report.md")
    ap.add_argument("--min-cut", type=float, default=config.MIN_CUT)
    ap.add_argument("--sentence-pause", type=float, default=config.SENTENCE_PAUSE)
    ap.add_argument("--extra-cuts", default=None,
                    help="JSON file with {'cut_word_indices': [...]} from Claude")
    a = ap.parse_args()
    transcript = json.loads(Path(a.transcript).read_text(encoding="utf-8"))
    extra = None
    if a.extra_cuts:
        extra = json.loads(Path(a.extra_cuts).read_text(encoding="utf-8")).get("cut_word_indices")
    edl = build_edl(transcript, min_cut=a.min_cut, sentence_pause=a.sentence_pause,
                    extra_cut_indices=extra)
    Path(a.out).write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(edl, transcript, a.report)
    print(f"kept {edl['stats']['kept_sec']}s / {edl['stats']['original_sec']}s "
          f"({edl['stats']['removed_pct']}% removed), "
          f"{edl['stats']['segments']} segments -> {a.out}, {a.report}")


if __name__ == "__main__":
    main()
