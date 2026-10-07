"""Turn a censor plan into an ffmpeg filter script.

Video: blur boxes (source pixels) -> 16:9 crop -> scale, output label ``[vout]``.
Audio: ``volume=0`` inside every mute window, output label ``[aout]`` (full
encode only — a preview has no audio).
"""
from __future__ import annotations
from pathlib import Path

_BOXBLUR = ("boxblur=luma_radius=min(h\\,w)/4:luma_power=4:"
            "chroma_radius=min(cw\\,ch)/4:chroma_power=4")


def build_filter(plan: dict, *, preview: str | None = None) -> str:
    """Filter-complex script for this plan.

    ``preview`` is a "WxH" override for a quick low-res check; it also drops the
    audio leg, so a preview renders in seconds.
    """
    blurs = plan.get("blur") or []
    crop = plan["crop"]
    n = len(blurs)

    parts = ["[0:v]split=%d[base]%s" % (n + 1, "".join(f"[s{i}]" for i in range(n)))]
    prev = "base"
    for i, b in enumerate(blurs):
        x, y, w, h = b["box"]
        enable = "+".join(f"between(t,{a},{z})" for a, z in b["windows"])
        parts.append(f"[s{i}]crop={w}:{h}:{x}:{y},{_BOXBLUR}[b{i}]")
        parts.append(f"[{prev}][b{i}]overlay={x}:{y}:enable='{enable}'[v{i}]")
        prev = f"v{i}"

    size = preview.replace("x", ":") if preview else f"{crop['out_w']}:{crop['out_h']}"
    parts.append(f"[{prev}]crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']},"
                 f"scale={size}[vout]")

    mutes = plan.get("mute") or []
    if not preview and mutes:
        enable = "+".join(f"between(t,{m['window'][0]},{m['window'][1]})" for m in mutes)
        parts.append(f"[0:a]volume=0:enable='{enable}'[aout]")
    return ";\n".join(parts)


def write_filter(plan: dict, out_path: str | Path, *, preview: str | None = None) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_filter(plan, preview=preview), encoding="utf-8")
    return out


def has_audio_leg(plan: dict, *, preview: str | None = None) -> bool:
    """True when the filter defines ``[aout]`` — i.e. the audio must be mapped
    from the filter graph rather than copied from the input."""
    return not preview and bool(plan.get("mute"))
