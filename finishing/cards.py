"""Card rendering — structured cards that preserve line hierarchy.

The first line is the title; the remaining lines become typed rows (bullets,
numbered steps, check marks, timeline nodes, chart bars). The canvas is sized
to the content, so a card grows with the number of rows.
"""
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlencode

_TEMPLATE = Path(__file__).resolve().parent / "templates" / "card.html"

# Tag shown above the title, per kind ("" = no tag).
_TAGS = {
    "side_card": "", "bottom_banner": "", "floating_label": "",
    "key_point_card": "Key Point", "process_flow": "Process",
    "checklist": "Checklist", "timeline": "Timeline",
    "comparison": "Comparison", "bar_chart": "", "quote": "",
    "stat_counter": "", "lower_third": "", "cta": "", "end_screen": "",
}

# Base canvas per kind; height grows with the number of rows.
_SIZES = {
    "stat_counter":  (820, 340),
    "quote":         (960, 380),
    "comparison":    (1040, 380),
    "bar_chart":     (980, 300),
    "lower_third":   (760, 220),
    "cta":           (820, 300),
    "process_flow":  (900, 320),
    "checklist":     (900, 320),
    "timeline":      (900, 320),
}
_DEFAULT_SIZE = (900, 300)
_ROW_PX = 46          # extra height per content row
_MAX_HEIGHT = 900


def card_size(kind: str, text: str) -> tuple[int, int]:
    w, h = _SIZES.get(kind, _DEFAULT_SIZE)
    rows = max(0, len([ln for ln in (text or "").split("\n") if ln.strip()]) - 1)
    if kind in ("stat_counter", "quote", "lower_third"):
        rows = min(rows, 1)
    if kind == "comparison":
        rows = 0
    return w, min(_MAX_HEIGHT, h + rows * _ROW_PX)


def render_card(out_png: str, *, title: str, subtitle: str = "",
                   accent_hex: str, kind: str = "side_card",
                   width: int | None = None, height: int | None = None) -> str:
    from playwright.sync_api import sync_playwright
    w, h = card_size(kind, title)
    if width:
        w = width
    if height:
        h = height
    params = {"title": title, "sub": subtitle, "accent": accent_hex,
              "kind": kind, "tag": _TAGS.get(kind, "")}
    url = _TEMPLATE.as_uri() + "?" + urlencode(params)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h},
                                device_scale_factor=2)
        page.emulate_media(color_scheme="dark")
        page.goto(url)
        page.screenshot(path=out_png, omit_background=True)
        browser.close()
    return out_png
