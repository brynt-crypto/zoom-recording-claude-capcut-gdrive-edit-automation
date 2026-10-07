"""Verify a censored master against its plan — never trust the encode blindly.

For every blur window the ORIGINAL (cropped and scaled the same way) is compared
with the CENSORED output inside the blur box at 10 fps. Text shows up as sharp
edges; a real blur removes them. A frame FAILS when the original has text edges
there and the censored copy keeps more than 25% of them.

Every mute window must also be digitally silent, and the durations must match.
An optional contact sheet of box crops is written for a human look.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

_EDGE = 60          # Laplacian magnitude counted as an edge pixel
_TEXT_EDGES = 80    # below this the original had nothing sharp to hide
_KEPT = 0.25        # fraction of the original's edges the blur may leave
_SILENT_DBFS = -60.0


def _np():
    import numpy as np
    return np


def out_box(box, crop) -> tuple[int, int, int, int]:
    """Source-pixel box -> its position in the cropped, scaled output."""
    sx, sy = crop["out_w"] / crop["w"], crop["out_h"] / crop["h"]
    x, y, w, h = box
    ox, oy = max(0, int((x - crop["x"]) * sx)), max(0, int((y - crop["y"]) * sy))
    ow = min(int(w * sx), crop["out_w"] - ox)
    oh = min(int(h * sy), crop["out_h"] - oy)
    return ox, oy, ow - ow % 2, oh - oh % 2


def _grab(path, t0, dur, box, crop, *, is_original: bool, ffmpeg="ffmpeg"):
    np = _np()
    ox, oy, ow, oh = box
    pre = (f"crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']},"
           f"scale={crop['out_w']}:{crop['out_h']}," if is_original else "")
    vf = f"fps=10,{pre}format=gray,crop={ow}:{oh}:{ox}:{oy}"
    raw = subprocess.run([ffmpeg, "-v", "error", "-ss", f"{t0}", "-t", f"{dur}",
                          "-i", str(path), "-vf", vf, "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, oh, ow).astype(np.int16)


def _edges(a):
    np = _np()
    lap = np.abs(4 * a[:, 1:-1, 1:-1] - a[:, :-2, 1:-1] - a[:, 2:, 1:-1]
                 - a[:, 1:-1, :-2] - a[:, 1:-1, 2:])
    return (lap > _EDGE).sum(axis=(1, 2))


def duration(path, ffprobe="ffprobe") -> float:
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def check_blurs(plan, original, censored, *, ffmpeg="ffmpeg") -> list[dict]:
    """One result row per blur window."""
    crop = plan["crop"]
    rows = []
    for b in plan.get("blur") or []:
        box = out_box(b["box"], crop)
        for a, z in b["windows"]:
            t0, dur = a + 0.05, (z - a) - 0.1
            o = _grab(original, t0, dur, box, crop, is_original=True, ffmpeg=ffmpeg)
            k = _grab(censored, t0, dur, box, crop, is_original=False, ffmpeg=ffmpeg)
            n = min(len(o), len(k))
            eo, ek = _edges(o[:n]), _edges(k[:n])
            fails = [(round(t0 + i / 10, 1), int(eo[i]), int(ek[i])) for i in range(n)
                     if eo[i] > _TEXT_EDGES and ek[i] > _KEPT * eo[i]]
            rows.append({"name": b["name"], "window": [a, z], "frames": n,
                         "orig_edges_max": int(eo.max()) if n else 0,
                         "censored_edges_max": int(ek.max()) if n else 0,
                         "fails": fails, "ok": not fails})
    return rows


def check_mutes(plan, censored, *, ffmpeg="ffmpeg") -> list[dict]:
    """One result row per mute window: the loudest sample must be inaudible."""
    np = _np()
    rows = []
    for m in plan.get("mute") or []:
        a, z = m["window"]
        raw = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(censored), "-vn", "-af",
             f"atrim=start={a + 0.03}:duration={z - a - 0.06},asetpts=PTS-STARTPTS",
             "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
            capture_output=True).stdout
        x = np.frombuffer(raw, np.float32)
        peak = float(20 * np.log10(np.abs(x).max() + 1e-12)) if len(x) else None
        rows.append({"name": m["name"], "window": [a, z], "peak_dbfs": peak,
                     "ok": peak is not None and peak < _SILENT_DBFS})
    return rows


def contact_sheet(plan, censored, out_png, *, extra_times=(), ffmpeg="ffmpeg",
                  cols: int = 6, pad: int = 40) -> Path | None:
    """First / middle / last frame of every blur window, as one sheet.

    ``extra_times`` adds frames at moments worth eyeballing (a card sliding in,
    a scroll that might outrun the box). Returns None without Pillow.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    crop = plan["crop"]
    spots = []
    for b in plan.get("blur") or []:
        for a, z in b["windows"]:
            spots += [(a + 0.05, b["box"]), ((a + z) / 2, b["box"]), (z - 0.05, b["box"])]
    first_box = (plan.get("blur") or [{}])[0].get("box")
    if first_box:
        spots += [(t, first_box) for t in extra_times]
    if not spots:
        return None

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_png.with_name("_censor_tile.png")
    tiles = []
    for t, bx in spots:
        ox, oy, ow, oh = out_box(bx, crop)
        x0, y0 = max(0, ox - pad), max(0, oy - pad)
        w0 = min(ow + 2 * pad, crop["out_w"] - x0)
        h0 = min(oh + 2 * pad, crop["out_h"] - y0)
        subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", f"{t}", "-i", str(censored),
                        "-frames:v", "1", "-vf",
                        f"crop={w0 - w0 % 2}:{h0 - h0 % 2}:{x0}:{y0}", str(tmp)])
        if not tmp.exists():
            continue
        im = Image.open(tmp).convert("RGB")
        im.thumbnail((480, 300))
        tile = Image.new("RGB", (480, 320), "black")
        tile.paste(im, (0, 20))
        ImageDraw.Draw(tile).text((4, 4), f"{t:.2f}", fill="yellow")
        tiles.append(tile)
    tmp.unlink(missing_ok=True)
    if not tiles:
        return None
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (480 * cols, 320 * rows))
    for i, tl in enumerate(tiles):
        sheet.paste(tl, ((i % cols) * 480, (i // cols) * 320))
    sheet.save(out_png)
    return out_png
