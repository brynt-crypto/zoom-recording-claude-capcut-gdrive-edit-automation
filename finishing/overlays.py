"""Overlay placement — animation vocabulary + staggered multi-layer beats.

  * resolves anim_in / anim_out through the tiered vocabulary (anim),
  * renders structured cards that keep their line hierarchy (cards),
  * supports `layers`, so a process flow / checklist / timeline reveals one row
    at a time instead of appearing all at once.

Staggering is done with real layers, not fake motion: layer N is a card PNG
containing rows 1..N, placed at final_in + offset and running to final_out. Each
new layer covers the previous one, so the list appears to build up.
"""
from __future__ import annotations
import os

from . import config, anim
from .cards import render_card

# treatment -> LAYOUT key
_PLACEMENT = {
    "left_card": "left_card", "right_card": "right_card",
    "bottom_banner": "bottom_banner", "floating_label": "floating_label",
    "pseudo_split": "pseudo_card",
    # Motion-graphic treatments share one band (top of frame, see _TOP_BAND) so cards never jump around.
    "process_flow": "left_card", "checklist": "left_card",
    "timeline": "left_card", "comparison": "bottom_banner",
    "bar_chart": "left_card", "quote": "bottom_banner",
    "stat_counter": "floating_label", "lower_third": "bottom_banner",
    "cta": "bottom_banner",
}

# treatment -> card kind for the renderer
_KIND = {
    "left_card": "side_card", "right_card": "side_card",
    "bottom_banner": "bottom_banner", "floating_label": "floating_label",
    "pseudo_split": "key_point_card",
    "process_flow": "process_flow", "checklist": "checklist",
    "timeline": "timeline", "comparison": "comparison",
    "bar_chart": "bar_chart", "quote": "quote",
    "stat_counter": "stat_counter", "lower_third": "lower_third", "cta": "cta",
}

CARD_TREATMENTS = frozenset(_PLACEMENT)

# Cards sit at the TOP of the frame, above the speaker's head (user decision
# 2026-09-10). The shared lower band (config.LAYOUT y=-0.55) cut across the
# speaker's face on camera shots, and any small raise covered MORE of it.
# Cards are pinned by their TOP edge rather than centred: a card grows taller
# with each row, so a fixed centre would push tall lists off the top of the
# frame. config.LAYOUT is left untouched, so the captions do not move.
_TOP_BAND = frozenset({"left_card", "right_card", "bottom_banner", "floating_label"})
_TOP_MARGIN = 0.004          # fallback: PNG box top, as a fraction of canvas height


def _png_size(path: str) -> tuple[int, int]:
    """Width/height from a PNG header (no Pillow dependency)."""
    with open(path, "rb") as f:
        head = f.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


_VISIBLE_TOP = 0.03         # visible card top, as a fraction of canvas height
_ALPHA_BODY = 200           # alpha above this is the card body, not its soft shadow


def _body_rows(png: str):
    """First/last pixel row of the opaque card body inside the PNG.

    card.html centres the card inside a taller transparent canvas and adds a
    soft drop shadow, so the PNG box top is NOT where the card starts. Measuring
    the opaque rows lets every card start at the same visible line.
    Returns None when Pillow/numpy are unavailable.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None
    alpha = np.asarray(Image.open(png).convert("RGBA"))[:, :, 3]
    rows = np.where((alpha > _ALPHA_BODY).any(axis=1))[0]
    return (int(rows[0]), int(rows[-1]) + 1) if rows.size else None


def _top_y(script, png: str, scale: float) -> float:
    """transform_y that puts the card's VISIBLE top at _VISIBLE_TOP of the frame.

    CapCut fits an image inside the canvas, then applies `scale`; transform_y is
    in half-canvas units with +1 at the top edge. Falls back to pinning the PNG
    box at _TOP_MARGIN if the body cannot be measured.
    """
    W, H = float(script.width), float(script.height)
    pw, ph = _png_size(png)
    k = min(W / pw, H / ph) * scale          # PNG px -> canvas px
    body = _body_rows(png)
    png_top = (_VISIBLE_TOP * H - body[0] * k) if body else _TOP_MARGIN * H
    return 1.0 - (png_top + ph * k / 2.0) / (H / 2.0)


def _secs(x: float) -> str:
    return f"{max(0.0, float(x)):.3f}s"


def _place(script, p, png, tx, ty, sc, start, dur, anim_in, anim_out, loop=None):
    mat = p.VideoMaterial(png)
    script.add_material(mat)
    seg = p.VideoSegment(
        mat, p.trange(_secs(start), _secs(dur)),
        clip_settings=p.ClipSettings(transform_x=tx, transform_y=ty,
                                     scale_x=sc, scale_y=sc),
    )
    # anim_in / anim_out may be None for the middle slices of a staggered
    # reveal, where an entrance on every row would re-animate the whole card.
    if anim_in:
        m_in, d_in = anim.resolve(p, anim.IMAGE_IN, anim_in, "IntroType")
        seg.add_animation(m_in, d_in)
    if anim_out:
        m_out, d_out = anim.resolve(p, anim.IMAGE_OUT, anim_out, "OutroType")
        seg.add_animation(m_out, d_out)
    script.add_segment(seg, track_name="overlay")
    return seg


def add_overlays(script, p, manifest, assets_dir, accent_hex) -> dict:
    """Place the cards. Returns a small summary for the build log."""
    beats = [b for b in manifest["beats"]
             if b["treatment"] in CARD_TREATMENTS and (b.get("text") or b.get("layers"))]
    summary = {"cards": 0, "layers": 0, "animations": set()}
    if not beats:
        return summary

    os.makedirs(assets_dir, exist_ok=True)
    script.add_track(p.TrackType.video, "overlay")

    for b in beats:
        tr = b["treatment"]
        kind = _KIND[tr]
        tx, ty, sc = config.LAYOUT[_PLACEMENT[tr]]
        top = _PLACEMENT[tr] in _TOP_BAND
        fi, fo = float(b["final_in"]), float(b["final_out"])
        accent = b.get("accent") or accent_hex
        anim_in = b.get("anim_in") or anim.DEFAULTS.get(tr, ("fade", "fade"))[0]
        anim_out = b.get("anim_out") or anim.DEFAULTS.get(tr, ("fade", "fade"))[1]
        summary["animations"].add(anim_in)

        layers = b.get("layers") or []
        if layers:
            # Cumulative reveal, played SEQUENTIALLY on one track.
            #
            # Layer i's PNG already contains rows 1..i+1, so showing the layers
            # back to back reads as a list building up one row at a time. They
            # must not overlap: a CapCut track rejects overlapping segments, and
            # stacking them on extra tracks would re-animate the whole card on
            # every row. Only the first slice gets the entrance animation and
            # only the last gets the exit, so the rows appear cleanly.
            head = (b.get("text") or "").strip()
            ordered = sorted(layers, key=lambda l: float(l.get("offset", 0.0)))
            starts = [fi + float(l.get("offset", 0.0)) for l in ordered]
            for i, layer in enumerate(ordered):
                start = starts[i]
                end = starts[i + 1] if i + 1 < len(starts) else fo
                if start >= fo or end <= start:
                    continue
                rows = [l.get("text", "") for l in ordered[: i + 1]]
                body = "\n".join([head] + rows) if head else "\n".join(rows)
                png = os.path.join(assets_dir, f"card_{b['id']}_{i}.png")
                if not os.path.exists(png):
                    render_card(png, title=body, accent_hex=accent, kind=kind)
                first, last = (i == 0), (i == len(ordered) - 1)
                l_anim = (layer.get("anim_in") or anim_in) if first else None
                _place(script, p, png, tx, _top_y(script, png, sc) if top else ty, sc,
                       start, end - start,
                       l_anim, anim_out if last else None)
                summary["layers"] += 1
                if l_anim:
                    summary["animations"].add(l_anim)
            summary["cards"] += 1
        else:
            png = os.path.join(assets_dir, f"card_{b['id']}.png")
            if not os.path.exists(png):
                render_card(png, title=b.get("text", ""),
                               subtitle=b.get("subtitle", ""),
                               accent_hex=accent, kind=kind)
            _place(script, p, png, tx, _top_y(script, png, sc) if top else ty, sc,
                   fi, fo - fi, anim_in, anim_out)
            summary["cards"] += 1

    summary["animations"] = sorted(summary["animations"])
    return summary
