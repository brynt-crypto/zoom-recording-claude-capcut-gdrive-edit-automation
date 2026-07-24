"""Assemble the polished CapCut draft from a rough-cut EDL + finishing manifest.

Only ever CREATES a new draft. CapCut must be CLOSED while writing.
Times: pycapcut treats bare numbers as microseconds; pass seconds as "1.5s"."""
from __future__ import annotations
import os
from pathlib import Path

from roughcut.mac_compat import make_mac_compatible

from . import config, beats
from .style import subtitle_style, subtitle_background
from .timemap import build_segments
from .assets_gen import probe_duration

# Mapping from beat treatment to LAYOUT key (for overlay positioning)
_PLACEMENT_KEY = {"left_card": "left_card", "right_card": "right_card",
                  "bottom_banner": "bottom_banner", "floating_label": "floating_label",
                  "pseudo_split": "pseudo_card"}

# Mapping from beat treatment to card kind (for render_card)
_CARD_KINDS = {"left_card": "side_card", "right_card": "side_card",
               "bottom_banner": "bottom_banner", "floating_label": "floating_label",
               "pseudo_split": "key_point_card"}


def _secs(x: float) -> str:
    return f"{max(0.0, float(x)):.3f}s"


def versioned_name(drafts_root: str, base: str) -> str:
    # First build keeps the clean base name; re-runs append " v2", " v3", … so a
    # re-edit never overwrites a draft already polished in CapCut.
    root = Path(drafts_root)
    if not (root / base).exists():
        return base
    i = 2
    while (root / f"{base} v{i}").exists():
        i += 1
    return f"{base} v{i}"


def add_base_track(script, p, edl, mat, mat_sec, intro_dur: float = 0.0,
                   intro_path=None, intro_zoom: bool = False):
    """Build the base video track. Returns (segs, seg_objs).

    mat        — already-created VideoMaterial for the source file
    intro_path — optional path to a company-intro clip to prepend at t=0
    intro_dur  — duration of the intro clip in seconds (pre-probed by caller);
                 keep-range segments start at this offset on the final timeline
    segs       — list of segment dicts from build_segments (keep ranges only)
    seg_objs   — parallel list of VideoSegment objects (None for skipped slivers);
                 corresponds 1-to-1 with segs (NOT including the intro segment)
                 so punch-in/pseudo-split indexing by keep-range stays correct
    """
    segs = build_segments(edl, intro_dur=intro_dur)
    script.add_material(mat)
    script.add_track(p.TrackType.video, "base")

    # Prepend the intro clip FIRST if provided, so it occupies [0, intro_dur).
    if intro_path and Path(intro_path).exists() and intro_dur > 0.0:
        intro_mat = p.VideoMaterial(intro_path)
        script.add_material(intro_mat)
        intro_mat_sec = intro_mat.duration / 1_000_000.0
        src_dur = min(intro_dur, intro_mat_sec)
        intro_vs = p.VideoSegment(
            intro_mat,
            p.trange(_secs(0.0), _secs(intro_dur)),
            source_timerange=p.trange(_secs(0.0), _secs(src_dur)),
        )
        script.add_segment(intro_vs, track_name="base")
        if intro_zoom:
            # Subtle quick push-in on the intro: zoom to 1.06 over the first
            # ~0.5s, then hold for the rest of the intro. Off by default so the
            # branded intro is never cropped/distorted unless explicitly asked.
            rise = min(0.5, intro_dur / 2.0)
            ks = p.KeyframeProperty.uniform_scale
            intro_vs.add_keyframe(ks, _secs(0.0), 1.0)
            intro_vs.add_keyframe(ks, _secs(rise), 1.06)
            intro_vs.add_keyframe(ks, _secs(intro_dur), 1.06)

    seg_objs = []
    for seg in segs:
        start = max(0.0, seg["src_start"])
        end = min(seg["src_end"], mat_sec)
        dur = end - start
        if dur <= 0.02:
            seg_objs.append(None)
            continue
        vs = p.VideoSegment(
            mat,
            p.trange(_secs(seg["final_start"]), _secs(dur)),
            source_timerange=p.trange(_secs(start), _secs(dur)),
        )
        script.add_segment(vs, track_name="base")
        seg_objs.append(vs)
    return segs, seg_objs


# Treatments that render their own on-screen text via a glass overlay/card (or
# the end-screen). These must NOT also get a lower-third subtitle — the card
# carries the copy, and a duplicate subtitle would be redundant and fight the
# card for placement. Only the subtitle_* treatments get a caption.
_CARD_TREATMENTS = frozenset({
    "left_card", "right_card", "bottom_banner", "floating_label",
    "pseudo_split", "end_screen",
})


def add_subtitles(script, p, manifest, accent_hex: str) -> None:
    script.add_track(p.TrackType.text, "subtitles")
    # Every caption uses the SAME lower-third position (shared with the cards),
    # so subtitles never shift height between beats.
    tx, ty, _ = config.LAYOUT["lower_third"]
    for b in manifest["beats"]:
        if b["treatment"] in _CARD_TREATMENTS:
            continue  # the glass card/overlay carries the text; no subtitle
        text = (b.get("text") or "").strip()
        if not text:
            continue
        fi, fo = float(b["final_in"]), float(b["final_out"])
        seg = p.TextSegment(
            text, p.trange(_secs(fi), _secs(fo - fi)),
            style=subtitle_style(bool(b.get("subtitle_emphasis")), accent_hex),
            background=subtitle_background(),
            clip_settings=p.ClipSettings(transform_x=tx, transform_y=ty),
        )
        seg.add_animation(p.TextIntro.渐显, "0.4s")
        seg.add_animation(p.TextOutro.渐隐, "0.4s")
        script.add_segment(seg, track_name="subtitles")


def add_caption_segments(script, p, captions, accent_hex: str) -> None:
    """Add continuous auto-captions (from finishing.captions) to the subtitle
    track at the shared lower-third position. Quick fades since captions change
    often. Used for long-form continuous captioning instead of manifest beats."""
    script.add_track(p.TrackType.text, "subtitles")
    tx, ty, _ = config.LAYOUT["lower_third"]
    for c in captions:
        fi, fo = float(c["final_in"]), float(c["final_out"])
        if fo - fi <= 0.02:
            continue
        seg = p.TextSegment(
            c["text"], p.trange(_secs(fi), _secs(fo - fi)),
            style=subtitle_style(False, accent_hex),
            background=subtitle_background(),
            clip_settings=p.ClipSettings(transform_x=tx, transform_y=ty),
        )
        seg.add_animation(p.TextIntro.渐显, "0.2s")
        seg.add_animation(p.TextOutro.渐隐, "0.2s")
        script.add_segment(seg, track_name="subtitles")


def add_overlays(script, p, manifest, assets_dir, accent_hex) -> None:
    """Place rendered glass-card PNGs on an 'overlay' video track.

    For each beat whose treatment is a card placement (left_card, right_card,
    bottom_banner, floating_label, pseudo_split) and has text, renders a PNG
    via render_card (if not already present) and places it at its LAYOUT
    position with fade in/out animations.
    """
    card_beats = [b for b in manifest["beats"]
                  if b["treatment"] in _PLACEMENT_KEY and (b.get("text"))]
    if not card_beats:
        return
    from .assets_gen import render_card
    os.makedirs(assets_dir, exist_ok=True)
    script.add_track(p.TrackType.video, "overlay")
    for b in card_beats:
        kind = _CARD_KINDS[b["treatment"]]
        png = os.path.join(assets_dir, f"card_{b['id']}.png")
        if not os.path.exists(png):
            render_card(png, title=b["text"], subtitle=b.get("subtitle", ""),
                        accent_hex=b.get("accent") or accent_hex, kind=kind)
        tx, ty, sc = config.LAYOUT[_PLACEMENT_KEY[b["treatment"]]]
        fi, fo = float(b["final_in"]), float(b["final_out"])
        mat = p.VideoMaterial(png)
        script.add_material(mat)
        seg = p.VideoSegment(
            mat, p.trange(_secs(fi), _secs(fo - fi)),
            clip_settings=p.ClipSettings(transform_x=tx, transform_y=ty,
                                         scale_x=sc, scale_y=sc),
        )
        seg.add_animation(p.IntroType.渐显, "0.4s")
        seg.add_animation(p.OutroType.渐隐, "0.4s")
        script.add_segment(seg, track_name="overlay")


def _overlapping_segment(segs, seg_objs, fi, fo):
    """Return (idx, seg) for the base segment that contains the beat MIDPOINT.

    Rule: a beat is assigned to exactly the one keep-range segment whose
    [final_start, final_end] interval contains the beat midpoint (fi+fo)/2.
    If a beat straddles a hard cut between two keep-range segments the segment
    containing the midpoint wins — effects (punch-in keyframes, pseudo-split
    keyframes) are clipped to that segment's local timeline, so no effect ever
    spans a cut boundary or modifies more than one base segment.

    Returns (None, None) when the midpoint falls outside every segment (e.g. it
    lies inside the intro or outro, or beyond the timeline).
    """
    mid = (fi + fo) / 2.0
    for idx, s in enumerate(segs):
        if s["final_start"] <= mid <= s["final_end"] and seg_objs[idx] is not None:
            return idx, seg_objs[idx]
    return None, None


def apply_punch_ins(p, segs, seg_objs, manifest) -> None:
    """Add a quick, elegant zoom (uniform_scale keyframes) on base segments.

    Processes beats with a numeric punch_in value, skipping pseudo_split beats.
    The zoom snaps in quickly when the beat (card/subtitle) appears, holds for
    the beat, then eases back out — rather than a slow symmetric pulse. Keyframe
    times are clipped to the overlapping segment's window.
    """
    for b in manifest["beats"]:
        if b["treatment"] == "pseudo_split":
            continue
        amt = b.get("punch_in")
        if amt is None or not isinstance(amt, (int, float)):
            continue
        fi, fo = float(b["final_in"]), float(b["final_out"])
        idx, seg = _overlapping_segment(segs, seg_objs, fi, fo)
        if seg is None:
            continue
        base = segs[idx]["final_start"]
        lo = max(0.0, fi - base)
        hi = min(segs[idx]["final_end"] - base, fo - base)
        # Quick in (~0.35s) → hold at the zoom → quick out (~0.35s). The rise is
        # clamped so the two middle keyframes never cross on short beats.
        rise = min(0.35, (hi - lo) / 2.0)
        ks = p.KeyframeProperty.uniform_scale
        seg.add_keyframe(ks, _secs(lo), 1.0)
        seg.add_keyframe(ks, _secs(lo + rise), float(amt))
        seg.add_keyframe(ks, _secs(hi - rise), float(amt))
        seg.add_keyframe(ks, _secs(hi), 1.0)


def apply_pseudo_split(p, segs, seg_objs, manifest) -> None:
    """Keyframe the overlapping base segment to the pseudo_speaker layout.

    For each pseudo_split beat, animates position_x and uniform_scale on the
    base segment to push the speaker left and shrink them, making room for
    the card overlay on the right.
    """
    tx, _, sc = config.LAYOUT["pseudo_speaker"]
    for b in manifest["beats"]:
        if b["treatment"] != "pseudo_split":
            continue
        fi, fo = float(b["final_in"]), float(b["final_out"])
        idx, seg = _overlapping_segment(segs, seg_objs, fi, fo)
        if seg is None:
            continue
        base = segs[idx]["final_start"]
        lo = max(0.0, fi - base)
        hi = min(segs[idx]["final_end"] - base, fo - base)
        # Clamp ramp so lo+ramp <= hi-ramp for any window (even < 0.8s beats).
        ramp = min(0.4, (hi - lo) / 2.0)
        # Animate position_x: 0.0 → tx → tx → 0.0 (ramp in/out)
        seg.add_keyframe(p.KeyframeProperty.position_x, _secs(lo), 0.0)
        seg.add_keyframe(p.KeyframeProperty.position_x, _secs(lo + ramp), tx)
        seg.add_keyframe(p.KeyframeProperty.position_x, _secs(hi - ramp), tx)
        seg.add_keyframe(p.KeyframeProperty.position_x, _secs(hi), 0.0)
        # Animate uniform_scale: 1.0 → sc → sc → 1.0
        # NOTE: uniform_scale internally maps to scale_x in pycapcut.
        # scale_y will remain unlinked; we accept this to avoid mixed-axis errors.
        seg.add_keyframe(p.KeyframeProperty.uniform_scale, _secs(lo), 1.0)
        seg.add_keyframe(p.KeyframeProperty.uniform_scale, _secs(lo + ramp), sc)
        seg.add_keyframe(p.KeyframeProperty.uniform_scale, _secs(hi - ramp), sc)
        seg.add_keyframe(p.KeyframeProperty.uniform_scale, _secs(hi), 1.0)


def add_full_clip(script, p, path, cursor: float) -> float:
    """Append an entire clip (e.g. the outro) at cursor on the 'base' track.

    Returns the new cursor position (cursor + clip duration in seconds).
    A fresh VideoMaterial is created here because this clip is a different file
    from the main source; the single-open rule only applies to edl["source"].
    """
    mat = p.VideoMaterial(path)
    script.add_material(mat)
    dur = mat.duration / 1_000_000.0
    seg = p.VideoSegment(mat, p.trange(_secs(cursor), _secs(dur)),
                         source_timerange=p.trange(_secs(0), _secs(dur)))
    script.add_segment(seg, track_name="base")
    return cursor + dur


def add_end_screen(script, p, edl, segs, assets_dir, accent_hex, mat, mat_sec,
                   name_title=None, dur: float = 5.0) -> float:
    """Append a masked speaker crop + end-card overlay to the timeline.

    mat and mat_sec are passed in from build() so we do NOT create a second
    VideoMaterial for edl["source"] — the single-open constraint is satisfied
    by the caller.

    Returns the new cursor position (seconds) after the end-screen window.
    """
    cursor = segs[-1]["final_end"] if segs else 0.0
    tail_start = max(0.0, mat_sec - dur)
    real = min(dur, mat_sec)

    from .assets_gen import render_card, extract_frame
    os.makedirs(assets_dir, exist_ok=True)

    # Speaker crop: a FREEZE-FRAME of the final frame (not a replay of the last
    # few seconds), masked to a rounded vertical rectangle, positioned left of
    # centre. Freezing avoids repeating the closing dialogue/motion that already
    # played at the end of the body. Falls back to the live tail if extraction
    # fails.
    tx, _, _ = config.LAYOUT["end_speaker"]
    clip = p.ClipSettings(transform_x=tx)
    freeze = extract_frame(edl["source"], os.path.join(assets_dir, "end_freeze.png"),
                           max(0.0, mat_sec - 0.15))
    if freeze:
        fmat = p.VideoMaterial(freeze)
        script.add_material(fmat)
        crop = p.VideoSegment(fmat, p.trange(_secs(cursor), _secs(real)),
                              clip_settings=clip)
    else:
        crop = p.VideoSegment(
            mat,
            p.trange(_secs(cursor), _secs(real)),
            source_timerange=p.trange(_secs(tail_start), _secs(real)),
            clip_settings=clip,
        )
    crop.add_mask(p.MaskType.矩形, size=0.9, round_corner=40.0, rect_width=0.42)
    crop.add_animation(p.IntroType.渐显, "0.5s")
    script.add_segment(crop, track_name="base")

    # Text card on the right side.
    title = "Thanks for watching"
    subtitle = ""
    if name_title and "|" in name_title:
        title, subtitle = name_title.split("|", 1)

    png = os.path.join(assets_dir, "end_card.png")
    render_card(png, title=title, subtitle=subtitle, accent_hex=accent_hex,
                kind="end_screen", width=900, height=500)
    cmat = p.VideoMaterial(png)
    script.add_material(cmat)
    cx, cy, _ = config.LAYOUT["end_card"]
    card = p.VideoSegment(cmat, p.trange(_secs(cursor), _secs(real)),
                          clip_settings=p.ClipSettings(transform_x=cx, transform_y=cy))
    card.add_animation(p.IntroType.渐显, "0.5s")
    # Ensure the overlay track exists (add_overlays only creates it when
    # there are card beats; end-screen may be the first thing to need it).
    if "overlay" not in script.tracks:
        script.add_track(p.TrackType.video, "overlay")
    script.add_segment(card, track_name="overlay")

    return cursor + real


def build(edl, manifest, draft_name, *, drafts_root, accent_hex,
          outro_path=None, intro_path: str | None = None,
          assets_dir=None, do_end_screen: bool = True,
          name_title=None, intro_zoom: bool = False, captions=None) -> str:
    import pycapcut as p
    manifest = beats.normalize(manifest)

    w = int(edl.get("width") or 1920)
    h = int(edl.get("height") or 1080)
    fps = int(round(float(edl.get("fps") or 30)))

    Path(drafts_root).mkdir(parents=True, exist_ok=True)
    name = versioned_name(drafts_root, draft_name)
    df = p.DraftFolder(drafts_root)
    script = df.create_draft(name, w, h, fps=fps)

    # Open VideoMaterial ONCE for edl["source"] — passed through to every
    # function that needs it to satisfy the single-open constraint.
    mat = p.VideoMaterial(edl["source"])
    mat_sec = mat.duration / 1_000_000.0

    # Compute intro duration from the real file so prep and build use the same
    # canonical offset — never trust a caller-supplied guess.
    intro_dur = probe_duration(intro_path) if (intro_path and Path(intro_path).exists()) else 0.0

    segs, seg_objs = add_base_track(script, p, edl, mat, mat_sec,
                                    intro_dur=intro_dur, intro_path=intro_path,
                                    intro_zoom=intro_zoom)
    assets_dir = assets_dir or str(Path(drafts_root).parent / "_cfe_assets" / name)
    add_overlays(script, p, manifest, assets_dir, accent_hex)
    apply_punch_ins(p, segs, seg_objs, manifest)
    apply_pseudo_split(p, segs, seg_objs, manifest)
    # Continuous auto-captions (long-form) take over the subtitle track; else
    # subtitles come from the manifest's subtitle_* beats.
    if captions is not None:
        add_caption_segments(script, p, captions, accent_hex)
    else:
        add_subtitles(script, p, manifest, accent_hex)

    cursor = segs[-1]["final_end"] if segs else intro_dur
    if do_end_screen:
        cursor = add_end_screen(script, p, edl, segs, assets_dir, accent_hex,
                                mat, mat_sec, name_title=name_title)
    if outro_path and Path(outro_path).exists():
        # Outro must remain the LAST clip on the base track; cursor is intentionally
        # discarded here — nothing follows the outro on this track.
        add_full_clip(script, p, outro_path, cursor)

    script.save()
    draft_path = str(Path(drafts_root) / name)
    # pycapcut writes the Windows draft layout; on macOS also emit draft_info.json
    # so CapCut for Mac can actually open it (no-ops on Windows).
    make_mac_compatible(draft_path)
    return draft_path
