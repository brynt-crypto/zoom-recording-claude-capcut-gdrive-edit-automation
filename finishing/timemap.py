"""Map rough-cut source time -> final-timeline time, and enrich the transcript.

The rough cut lays kept ranges end-to-end (optionally after an intro clip).
A source time inside a kept range has a final-timeline position; a source time
inside a cut has none. All times are SECONDS (floats)."""
from __future__ import annotations


def build_segments(edl: dict, intro_dur: float = 0.0) -> list[dict]:
    segs: list[dict] = []
    cursor = float(intro_dur)
    for r in edl["keep"]:
        s, e = float(r["start"]), float(r["end"])
        dur = e - s
        if dur <= 0:
            continue
        segs.append({"src_start": s, "src_end": e,
                     "final_start": cursor, "final_end": cursor + dur})
        cursor += dur
    return segs


def src_to_final(t: float, segments: list[dict]) -> float | None:
    for seg in segments:
        if seg["src_start"] <= t <= seg["src_end"]:
            return seg["final_start"] + (t - seg["src_start"])
    return None


def enrich_transcript(transcript: dict, edl: dict, intro_dur: float = 0.0) -> dict:
    segs = build_segments(edl, intro_dur=intro_dur)
    final_duration = segs[-1]["final_end"] if segs else 0.0
    words_out = []
    for w in transcript["words"]:
        fs = src_to_final(float(w["start"]), segs)
        fe = src_to_final(float(w["end"]), segs)
        if fs is None or fe is None:
            continue  # word fell inside a cut
        words_out.append({"i": w["i"], "src_start": w["start"], "src_end": w["end"],
                          "final_start": round(fs, 3), "final_end": round(fe, 3),
                          "text": w["text"]})
    return {"source": transcript["source"], "fps": transcript.get("fps", 30),
            "width": transcript.get("width", 1920), "height": transcript.get("height", 1080),
            "final_duration": round(final_duration, 3), "words": words_out}
