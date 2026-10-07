"""Censor spoken words in the finished video: duck the dialogue, lay a tone over it.

Given phrases to censor, this finds every spoken occurrence in the FINAL
timeline (using transcript_final.json word timings), then:

  * keyframes the overlapping base segment's `volume` to 0 across the window,
    with short ramps so the duck does not click, and
  * places a 1 kHz tone on a dedicated "bleep" audio track for exactly that span.

The caption text is NOT handled here — captions come from transcript_final.json,
so the words must be substituted there as well or the viewer simply reads what
they cannot hear.
"""
from __future__ import annotations
import os
import re
import subprocess

# Ramp in/out of the duck, seconds. Long enough to avoid a click, short enough
# that no syllable of the censored word survives.
RAMP = 0.04
# Pad the window slightly so onset/offset of the word is fully covered.
PAD = 0.06
BEEP_HZ = 1000
BEEP_GAIN = 0.18          # quiet enough to sit under a normal mix


def _secs(x: float) -> str:
    return f"{max(0.0, float(x)):.3f}s"


def find_windows(words: list[dict], phrases: list[str]) -> list[tuple[float, float, str]]:
    """Locate every spoken occurrence of each phrase in the final timeline.

    Matching is token-wise and case/punctuation insensitive, so "Acme Insurance",
    "acme insurance." and "Acme Insurances" all match the phrase "acme insurance".
    """
    norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
    toks = [norm(w.get("text", "")) for w in words]
    out: list[tuple[float, float, str]] = []
    for phrase in phrases:
        parts = [norm(p) for p in phrase.split() if norm(p)]
        if not parts:
            continue
        n = len(parts)
        for i in range(len(toks) - n + 1):
            window = toks[i:i + n]
            # allow a trailing plural on the last token ("farms")
            if window[:-1] == parts[:-1] and window[-1] in (parts[-1], parts[-1] + "s"):
                out.append((float(words[i]["final_start"]),
                            float(words[i + n - 1]["final_end"]), phrase))
    out.sort(key=lambda w: w[0])
    # merge any overlapping/adjacent windows so the duck is one continuous ramp
    merged: list[list] = []
    for a, b, ph in out:
        if merged and a - merged[-1][1] < 0.05:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b, ph])
    return [(a, b, ph) for a, b, ph in merged]


def render_beep(out_wav: str, duration: float, ffmpeg: str = "ffmpeg") -> str | None:
    """Render a short sine tone. Returns None if ffmpeg is unavailable."""
    os.makedirs(os.path.dirname(out_wav) or ".", exist_ok=True)
    dur = max(0.05, float(duration))
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
           "-i", f"sine=frequency={BEEP_HZ}:duration={dur:.3f}",
           "-af", f"volume={BEEP_GAIN},afade=t=in:d=0.01,"
                  f"afade=t=out:st={max(0.0, dur - 0.01):.3f}:d=0.01",
           "-ar", "48000", "-ac", "2", "-y", out_wav]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception:
        return None
    return out_wav if os.path.exists(out_wav) else None


def duck_base_audio(p, segs, seg_objs, windows, overlapping) -> int:
    """Keyframe base-segment volume to 0 across each window. Returns count applied."""
    applied = 0
    for start, end, _ph in windows:
        lo_t, hi_t = start - PAD, end + PAD
        idx, seg = overlapping(segs, seg_objs, lo_t, hi_t)
        if seg is None:
            continue
        base = segs[idx]["final_start"]
        seg_end = segs[idx]["final_end"]
        lo = max(0.0, lo_t - base)
        hi = min(seg_end - base, hi_t - base)
        if hi <= lo:
            continue
        ramp = min(RAMP, (hi - lo) / 3.0)
        kv = p.KeyframeProperty.volume
        seg.add_keyframe(kv, _secs(max(0.0, lo - ramp)), 1.0)
        seg.add_keyframe(kv, _secs(lo), 0.0)
        seg.add_keyframe(kv, _secs(hi), 0.0)
        seg.add_keyframe(kv, _secs(min(seg_end - base, hi + ramp)), 1.0)
        applied += 1
    return applied


def add_bleep_track(script, p, windows, assets_dir, ffmpeg="ffmpeg") -> int:
    """Place a tone over each window on its own audio track. Returns count placed."""
    if not windows:
        return 0
    placed = 0
    script.add_track(p.TrackType.audio, "bleep")
    for i, (start, end, _ph) in enumerate(windows):
        dur = (end + PAD) - (start - PAD)
        # Name by duration, not just index: window indices shift when a window is
        # added or removed, and a cached tone of the wrong length would be reused
        # (CapCut then rejects the segment as longer than its material).
        wav = os.path.join(assets_dir, f"bleep_{i}_{int(round(dur * 1000))}ms.wav")
        if not os.path.exists(wav):
            if render_beep(wav, dur, ffmpeg=ffmpeg) is None:
                continue
        mat = p.AudioMaterial(wav)
        script.add_material(mat)
        seg = p.AudioSegment(mat, p.trange(_secs(max(0.0, start - PAD)), _secs(dur)))
        script.add_segment(seg, track_name="bleep")
        placed += 1
    return placed
