"""Auto-generate continuous lower-third captions from an enriched transcript.

Chunks the word list (each with final_start/final_end) into short, readable
caption segments (≈1–2 lines), splitting on sentence-ending punctuation, a max
character length, a max duration, or a speech gap. Captions that overlap a
card/overlay window are dropped so the card's own text is never doubled by a
caption underneath it.
"""
from __future__ import annotations

_SENTENCE_END = (".", "?", "!", "…")


def _overlaps(cap: dict, windows) -> bool:
    return any(not (cap["final_out"] <= s or cap["final_in"] >= e) for s, e in windows)


def wrap_two_lines(text: str, per_line: int) -> str:
    """Wrap `text` into AT MOST two lines, breaking ONLY at spaces.

    Never splits inside a word — so contractions like "we've"/"I'll" always stay
    intact on one line. Picks the space that best balances the two lines (and,
    where possible, keeps each line within `per_line`). Returns the text with a
    single embedded newline, or unchanged if it already fits on one line.
    """
    text = text.strip()
    if len(text) <= per_line:
        return text
    words = text.split()
    if len(words) < 2:
        return text  # a single long token — nothing safe to break on
    best = None
    for i in range(1, len(words)):
        l1 = " ".join(words[:i])
        l2 = " ".join(words[i:])
        over = 1000 if max(len(l1), len(l2)) > per_line else 0
        score = over + abs(len(l1) - len(l2))
        if best is None or score < best[0]:
            best = (score, l1, l2)
    return best[1] + "\n" + best[2]


def build_captions(words, card_windows=(), *, max_chars: int = 44,
                   max_gap: float = 0.8, max_dur: float = 6.0,
                   per_line: int = 24) -> list[dict]:
    """Return a list of {text, final_in, final_out} caption segments.

    A new caption starts when adding the next word would exceed `max_chars`,
    span more than `max_dur` seconds, or follow a silence gap > `max_gap`.
    A caption also ends right after a word ending in sentence punctuation.

    `max_chars` is kept low and each caption is pre-wrapped into AT MOST two
    lines (`per_line` chars each, broken only at spaces) so captions never grow
    to three lines and never split a word/contraction across a line break.
    """
    caps: list[dict] = []
    cur: list[dict] = []

    def flush():
        if not cur:
            return
        text = " ".join(w["text"] for w in cur).strip()
        if text:
            caps.append({"text": wrap_two_lines(text, per_line),
                         "final_in": round(cur[0]["final_start"], 3),
                         "final_out": round(cur[-1]["final_end"], 3)})
        cur.clear()

    for w in words:
        if cur:
            gap = w["final_start"] - cur[-1]["final_end"]
            cand_len = len(" ".join(x["text"] for x in cur)) + 1 + len(w["text"])
            dur = w["final_end"] - cur[0]["final_start"]
            if gap > max_gap or cand_len > max_chars or dur > max_dur:
                flush()
        cur.append(w)
        if w["text"].strip().endswith(_SENTENCE_END):
            flush()
    flush()

    return [c for c in caps if not _overlaps(c, card_windows)]
