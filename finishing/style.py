"""Pure helpers turning the palette into pycapcut style objects."""
from __future__ import annotations

from . import config


def hex_to_rgb01(hex_str: str) -> tuple[float, float, float]:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def subtitle_style(emphasis: bool, accent_hex: str):
    from pycapcut import TextStyle
    # Consistent font size across all captions (emphasis changes weight + color,
    # NOT size) so subtitles read evenly and don't jump in scale. Kept a touch
    # smaller so captions sit comfortably and match the card text scale.
    return TextStyle(
        size=5.0,
        bold=emphasis,
        color=hex_to_rgb01(accent_hex) if emphasis else (1.0, 1.0, 1.0),
        align=1,                 # centered
        # Captions are pre-wrapped to <=2 lines at spaces (see captions.py). Auto
        # wrapping is OFF so CapCut renders our line breaks verbatim and never
        # re-splits a word/contraction (e.g. "we've") at a line boundary.
        auto_wrapping=False,
        max_line_width=0.46,     # kept as a safety bound for the bar width
    )


def subtitle_background():
    from pycapcut import TextBackground
    # Rounded translucent near-black bar behind the caption for readability.
    return TextBackground(color=config.GLASS_BASE_HEX, alpha=0.55,
                          round_radius=0.3, height=0.10, width=0.50)


def resolve_font(name: str):
    """Return the matching FontType member, or None to use the system default."""
    from pycapcut import FontType
    try:
        return getattr(FontType, name)
    except AttributeError:
        return None
