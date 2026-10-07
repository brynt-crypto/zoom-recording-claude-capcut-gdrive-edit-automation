"""Build an editable CapCut draft from an EDL (one keep-range = one segment).

Uses pycapcut. Each keep-range becomes a VideoSegment whose:
  - source_timerange = where it lives in the original clip (in/out point)
  - target_timerange = where it sits on the timeline (laid end-to-end)
so opening the draft in CapCut shows the raw clip pre-cut, every cut still
draggable/restorable.

IMPORTANT: pycapcut's trange() treats floats as MICROSECONDS; pass seconds as
strings like "1.5s". CapCut must be CLOSED while writing (it overwrites drafts
from memory on exit).

Safety: only ever CREATES a new draft folder; never edits existing drafts.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from .mac_compat import make_mac_compatible

# Default CapCut International drafts root. On macOS CapCut stores drafts under
# ~/Movies/CapCut/...; on Windows it's %LOCALAPPDATA%\CapCut\... (unchanged).
# This constant is re-exported to the finishing engine via finishing/config.py,
# so branching it here makes both engines write to the right place per-OS.
if sys.platform == "darwin":
    DEFAULT_DRAFTS_ROOT = os.path.expanduser(
        "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
    )
else:
    DEFAULT_DRAFTS_ROOT = os.path.expandvars(
        r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft"
    )


def _secs(x: float) -> str:
    return f"{max(0.0, float(x)):.3f}s"


def _add_full_clip(script, p, path: str, cursor: float) -> float:
    """Add an entire clip (intro/outro) at `cursor`; return new cursor."""
    mat = p.VideoMaterial(path)
    script.add_material(mat)
    dur = mat.duration / 1_000_000.0
    seg = p.VideoSegment(
        mat,
        p.trange(_secs(cursor), _secs(dur)),
        source_timerange=p.trange(_secs(0), _secs(dur)),
    )
    script.add_segment(seg)
    return cursor + dur


def _versioned_name(drafts_root: str, base: str) -> str:
    """Return `base` if free, else base_v2, base_v3, ... so a re-edit never
    overwrites a draft already polished in CapCut."""
    root = Path(drafts_root)
    if not (root / base).exists():
        return base
    i = 2
    while (root / f"{base}_v{i}").exists():
        i += 1
    return f"{base}_v{i}"


# Every Zoom edit is delivered 16:9 at 1920x1080, whatever the recording's size
# (standing rule, 2026-09-14). CapCut fits each clip into this canvas.
CANVAS_W, CANVAS_H = 1920, 1080


def force_canvas_16x9(draft_path: str | Path) -> None:
    """Pin the draft canvas to an explicit 16:9 1920x1080.

    pycapcut always writes ``"ratio": "original"``, and CapCut then resizes the
    canvas to the first clip when it opens the draft (the 1920x1016 intro turned
    a 1920x1080 edit into 1920x1016). An explicit "16:9" ratio stops that.
    """
    import json
    for fname in ("draft_content.json", "draft_info.json"):
        f = Path(draft_path) / fname
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        data["canvas_config"] = {"width": CANVAS_W, "height": CANVAS_H, "ratio": "16:9"}
        f.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def build(edl: dict, draft_name: str, *,
          drafts_root: str = DEFAULT_DRAFTS_ROOT,
          allow_replace: bool = False,
          versioned: bool = True,
          intro_path: str | None = None,
          outro_path: str | None = None) -> str:
    import pycapcut as p

    src = edl["source"]
    if not Path(src).exists():
        raise FileNotFoundError(f"source video not found: {src}")
    keep = edl["keep"]
    if not keep:
        raise RuntimeError("EDL has no keep ranges")

    w, h = CANVAS_W, CANVAS_H
    fps = int(round(float(edl.get("fps") or 30)))

    Path(drafts_root).mkdir(parents=True, exist_ok=True)
    # Auto-version on re-edit unless an explicit overwrite was requested.
    if versioned and not allow_replace:
        draft_name = _versioned_name(drafts_root, draft_name)
    df = p.DraftFolder(drafts_root)
    script = df.create_draft(draft_name, w, h, fps=fps, allow_replace=allow_replace)

    mat = p.VideoMaterial(src)
    script.add_material(mat)
    script.add_track(p.TrackType.video)

    # pycapcut reads the true stream duration (may be a few ms shorter than
    # ffprobe's container duration); clamp source ranges so the last segment
    # never overshoots the material length.
    mat_sec = mat.duration / 1_000_000.0

    cursor = 0.0
    # Intro: full clip at the very front (separate, editable segment).
    if intro_path and Path(intro_path).exists():
        cursor = _add_full_clip(script, p, intro_path, cursor)

    for r in keep:
        start = max(0.0, r["start"])
        end = min(r["end"], mat_sec)
        dur = end - start
        if dur <= 0.02:
            continue
        seg = p.VideoSegment(
            mat,
            p.trange(_secs(cursor), _secs(dur)),
            source_timerange=p.trange(_secs(start), _secs(dur)),
        )
        script.add_segment(seg)
        cursor += dur

    # Outro: full clip appended at the end.
    if outro_path and Path(outro_path).exists():
        cursor = _add_full_clip(script, p, outro_path, cursor)

    script.save()
    draft_path = str(Path(drafts_root) / draft_name)
    # pycapcut writes the Windows draft layout; on macOS also emit draft_info.json
    # so CapCut for Mac can actually open it (no-ops on Windows).
    make_mac_compatible(draft_path)
    force_canvas_16x9(draft_path)
    return draft_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a CapCut draft from an EDL")
    ap.add_argument("edl")
    ap.add_argument("--name", required=True, help="draft name (folder under drafts root)")
    ap.add_argument("--drafts-root", default=DEFAULT_DRAFTS_ROOT)
    ap.add_argument("--allow-replace", action="store_true")
    ap.add_argument("--intro", default=None)
    ap.add_argument("--outro", default=None)
    a = ap.parse_args()
    edl = json.loads(Path(a.edl).read_text(encoding="utf-8"))
    path = build(edl, a.name, drafts_root=a.drafts_root, allow_replace=a.allow_replace,
                 intro_path=a.intro, outro_path=a.outro)
    print(f"draft written -> {path}")
    print(f"segments: {len(edl['keep'])}  (open CapCut to edit; CapCut must have been CLOSED when this ran)")


if __name__ == "__main__":
    main()
