"""Assemble the animated CapCut draft from a storyboard + generated stills.

Tracks:
  base       — one image VideoSegment per scene, laid contiguous from 0s, each
               animated with Ken Burns keyframes (animate.motion).
  narration  — one AudioSegment carrying the user's original narration.
  subtitles  — per-scene caption TextSegments (only scenes with a caption).
Optional intro/outro branding clips bookend the base track.

Only ever CREATES a new (auto-versioned) draft. CapCut must be CLOSED while
writing. pycapcut treats bare numbers as microseconds; pass seconds as "1.5s".
"""
from __future__ import annotations
from pathlib import Path

from . import config, motion


def _secs(x: float) -> str:
    return f"{max(0.0, float(x)):.3f}s"


def versioned_name(drafts_root: str, base: str) -> str:
    """base -> base, then 'base v2', 'base v3', … so a polished draft is never
    overwritten (mirrors finishing.build_finish.versioned_name)."""
    root = Path(drafts_root)
    if not (root / base).exists():
        return base
    i = 2
    while (root / f"{base} v{i}").exists():
        i += 1
    return f"{base} v{i}"


def _caption_style(p, emphasis: bool):
    from pycapcut import TextStyle
    h = config.ACCENT_HEX.lstrip("#")
    accent = (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)
    return TextStyle(size=8.0 if emphasis else 6.0, bold=True,
                     color=accent if emphasis else (1.0, 1.0, 1.0), align=1)


def _caption_bg(p):
    from pycapcut import TextBackground
    return TextBackground(color=config.GLASS_BASE_HEX, alpha=0.55,
                          round_radius=0.3, height=0.10, width=0.50)


def _add_full_clip(script, p, path: str, cursor: float) -> float:
    """Append an intro/outro clip on the base track at `cursor`. Returns new cursor."""
    mat = p.VideoMaterial(path)
    script.add_material(mat)
    dur = mat.duration / 1_000_000.0
    seg = p.VideoSegment(mat, p.trange(_secs(cursor), _secs(dur)),
                         source_timerange=p.trange(_secs(0), _secs(dur)))
    script.add_segment(seg, track_name="base")
    return cursor + dur


def build(job: str, scenes: list[dict], audio_path: str, scenes_dir: str,
          draft_name: str, *, drafts_root: str = config.DRAFTS_ROOT,
          intro_path: str | None = None, outro_path: str | None = None) -> dict:
    import pycapcut as p

    scenes_dir = Path(scenes_dir)
    if not scenes:
        raise RuntimeError("storyboard has no scenes")
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"narration audio not found: {audio_path}")

    Path(drafts_root).mkdir(parents=True, exist_ok=True)
    name = versioned_name(drafts_root, draft_name)
    df = p.DraftFolder(drafts_root)
    script = df.create_draft(name, config.CANVAS_W, config.CANVAS_H, fps=config.FPS)

    script.add_track(p.TrackType.video, "base")

    # Intro branding first so it occupies [0, intro_dur); scenes then start at
    # intro_dur and stay contiguous (base-track segments must start at 0s).
    intro_dur = 0.0
    if intro_path and Path(intro_path).exists():
        intro_dur = _add_full_clip(script, p, intro_path, 0.0)

    missing: list[int] = []
    scene_end = intro_dur
    for s in scenes:
        sid = int(s["id"])
        png = scenes_dir / f"scene_{sid}.png"
        if not png.exists():
            missing.append(sid)
            continue
        start = intro_dur + float(s["start"])
        dur = float(s["end"]) - float(s["start"])
        if dur <= 0.02:
            continue
        mat = p.VideoMaterial(str(png))
        script.add_material(mat)
        # Photo material: omit source_timerange (mirrors finishing overlays).
        seg = p.VideoSegment(mat, p.trange(_secs(start), _secs(dur)))
        mot = s.get("motion", "static")
        if s.get("emphasis") and mot == "static":
            mot = "zoom_in"  # emphasised beats always get a little push-in
        motion.apply(seg, p, mot, dur)
        seg.add_animation(p.IntroType.渐显, _secs(config.SCENE_FADE))
        script.add_segment(seg, track_name="base")
        scene_end = start + dur

    if missing:
        raise RuntimeError(
            f"missing scene images for ids {missing} — run --generate first "
            f"(or --dry-run to build with placeholders)")

    # Narration: aligned to start where the scenes start (after any intro).
    narr_mat = p.AudioMaterial(str(audio_path))
    script.add_material(narr_mat)
    narr_sec = narr_mat.duration / 1_000_000.0
    # Clamp so the segment never overshoots the material or the scene coverage.
    narr_dur = min(narr_sec, scene_end - intro_dur)
    script.add_track(p.TrackType.audio, "narration")
    a_seg = p.AudioSegment(narr_mat, p.trange(_secs(intro_dur), _secs(narr_dur)),
                           source_timerange=p.trange(_secs(0), _secs(narr_dur)))
    a_seg.add_fade("0.05s", "0.4s")
    script.add_segment(a_seg, track_name="narration")

    # Per-scene captions (lower third).
    cap_scenes = [s for s in scenes if (s.get("caption") or "").strip()]
    if cap_scenes:
        script.add_track(p.TrackType.text, "subtitles")
        for s in cap_scenes:
            start = intro_dur + float(s["start"])
            dur = float(s["end"]) - float(s["start"])
            seg = p.TextSegment(
                s["caption"].strip(), p.trange(_secs(start), _secs(dur)),
                style=_caption_style(p, bool(s.get("emphasis"))),
                background=_caption_bg(p),
                clip_settings=p.ClipSettings(transform_x=0.0, transform_y=-0.55),
            )
            seg.add_animation(p.TextIntro.渐显, "0.3s")
            seg.add_animation(p.TextOutro.渐隐, "0.3s")
            script.add_segment(seg, track_name="subtitles")

    # Outro branding last on the base track.
    if outro_path and Path(outro_path).exists():
        _add_full_clip(script, p, outro_path, scene_end)

    script.save()
    return {"draft_path": str(Path(drafts_root) / name), "name": name,
            "n_scenes": len(scenes), "n_captions": len(cap_scenes),
            "intro_dur": round(intro_dur, 3)}
