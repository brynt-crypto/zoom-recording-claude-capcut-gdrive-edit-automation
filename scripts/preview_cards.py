#!/usr/bin/env python3
"""Contact sheet of a finished draft's cards composited onto real frames.

Reads the card PNGs and their transforms out of a CapCut draft and places them
over frames of the source video exactly the way CapCut positions them — so you
can check placement, size and legibility without opening CapCut.

Usage:
  python scripts/preview_cards.py <job> <out.png> [--samples 12] [--draft NAME]

``--draft`` picks the draft by name (the newest match wins); the default is the
newest draft whose name starts with the job's prettified title.
"""
from __future__ import annotations
import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import job_dir                          # noqa: E402
from roughcut.build_draft import DEFAULT_DRAFTS_ROOT      # noqa: E402

_GROUP = 3.0        # card starts within this many seconds are the same moment
_INTO_CARD = 2.8    # sample this far into a card, so its entrance has finished


def find_draft(job: str, pattern: str | None) -> Path:
    root = Path(DEFAULT_DRAFTS_ROOT)
    glob = f"{pattern}*" if pattern else f"{job.replace('_', ' ').title()}*"
    drafts = sorted(root.glob(glob), key=lambda p: p.stat().st_mtime)
    if not drafts:
        sys.exit(f"no draft matching {glob!r} under {root}")
    return drafts[-1]


def draft_json(draft: Path) -> dict:
    for name in ("draft_info.json", "draft_content.json"):
        f = draft / name
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    sys.exit(f"{draft} has no draft_info.json / draft_content.json")


def png_segments(dj: dict) -> list[tuple]:
    """(start_seconds, png_path, transform_x, transform_y, scale) per card."""
    mats = {v["id"]: v for v in dj["materials"]["videos"]}
    segs = []
    for tr in dj["tracks"]:
        for s in tr.get("segments", []):
            mt = mats.get(s.get("material_id"))
            if mt and mt.get("path", "").lower().endswith(".png"):
                c = s["clip"]
                segs.append((s["target_timerange"]["start"] / 1e6, mt["path"],
                             c["transform"]["x"], c["transform"]["y"], c["scale"]["x"]))
    segs.sort()
    return segs


def source_time(t: float, keep: list[dict], intro: float) -> float:
    """Timeline seconds -> seconds in the source recording."""
    t -= intro
    acc = 0.0
    for k in keep:
        d = k["end"] - k["start"]
        if t < acc + d:
            return k["start"] + (t - acc)
        acc += d
    return keep[-1]["end"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("out")
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--draft", default=None, help="draft name prefix to match")
    ap.add_argument("--intro", type=float, default=5.0,
                    help="length of the intro clip in front of the content")
    ap.add_argument("--cols", type=int, default=3)
    args = ap.parse_args()

    from PIL import Image

    jd = job_dir(args.job, create=False)
    draft = find_draft(args.job, args.draft)
    dj = draft_json(draft)
    W, H = dj["canvas_config"]["width"], dj["canvas_config"]["height"]
    segs = png_segments(dj)
    if not segs:
        sys.exit(f"{draft.name} has no card PNGs on its timeline")

    edl = json.loads((jd / "edl.json").read_text(encoding="utf-8"))
    keep = edl["keep"]

    starts: list[float] = []
    for st, *_ in segs:
        if not any(abs(st - s0) < _GROUP for s0 in starts):
            starts.append(st)
    step = max(1, len(starts) // args.samples)
    picks = starts[::step][:args.samples]

    tiles = []
    for t0 in picks:
        t = t0 + _INTO_CARD
        src = source_time(t, keep, args.intro)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{src}", "-i", edl["source"],
                              "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                             capture_output=True).stdout
        if not raw:
            print(f"  (no frame at {src:.1f}s — skipped)")
            continue
        frame = Image.open(io.BytesIO(raw)).convert("RGBA").resize((W, H))
        for st, png, x, y, sc in segs:
            if abs(st - t0) < _GROUP and st <= t:
                im = Image.open(png).convert("RGBA")
                pw, ph = im.size
                k = min(W / pw, H / ph) * sc
                im = im.resize((max(1, int(pw * k)), max(1, int(ph * k))))
                cx, cy = W / 2 + x * W / 2, H / 2 - y * H / 2
                frame.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))
        tiles.append(frame.convert("RGB").resize((640, int(640 * H / W))))
        print(f"  card at {t0:7.1f}s (source {src:7.1f}s)")

    if not tiles:
        sys.exit("nothing to composite")
    th = tiles[0].height
    rows = (len(tiles) + args.cols - 1) // args.cols
    sheet = Image.new("RGB", (640 * args.cols, th * rows))
    for i, tl in enumerate(tiles):
        sheet.paste(tl, ((i % args.cols) * 640, (i // args.cols) * th))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"draft: {draft.name} | canvas {W}x{H} | {len(segs)} card segments | sheet {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
