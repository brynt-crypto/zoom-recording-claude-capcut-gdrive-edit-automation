# CapCut Finishing Editor (CFE) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `finishing/` engine + a `CapCut finishing editor.md` skill that turns a completed rough-cut job into a polished, premium dark-tech/liquid-glass CapCut draft (subtitles, glass-card overlays, punch-ins, pseudo-split, end-screen) — with a human review gate before building.

**Architecture:** Mirrors `roughcut/`. The Python engine is **deterministic**: it maps rough-cut source-time → final-timeline-time, renders glass-card PNGs from HTML templates, and assembles a CapCut draft via `pycapcut`. **Claude does the semantic work** — it reads the enriched transcript and writes `finishing_manifest.json` (exactly like roughcut's `semantic_cuts.json`). The engine then validates that manifest, generates assets, and builds the draft.

**Tech Stack:** Python 3.12 (project `.venv`), `pycapcut` (CapCut draft writer), `playwright` (headless Chromium → transparent PNG), `ffmpeg` (style-ref frame sampling), `pytest`.

## Global Constraints

- **Runtime:** always the project venv — `./.venv/Scripts/python.exe -m finishing.pipeline ...`. Platform Windows.
- **Never re-cut:** the engine must not remove words/filler/dead-air or alter the rough-cut keep ranges. Polish only.
- **Safety:** only ever CREATE a new draft folder; never modify an existing draft. CapCut must be CLOSED when writing (it overwrites drafts from memory on exit).
- **Output naming (verbatim):** CapCut draft folder = `<job>_(CFE Edit)_v1`, auto-incrementing `_v2`, `_v3` on re-runs. Always versioned, starting at `v1`.
- **pycapcut gotchas (verbatim):** time strings use seconds suffix `"1.5s"`; bare `int`/`float` = **microseconds**. `ClipSettings.transform_x/y` and `KeyframeProperty.position_x/y` are in **half-canvas units** (1.0 = canvas edge). `add_mask center_x/center_y` are in **pixels**; `size` is a proportion of material height; `feather`/`round_corner` are 0–100. Animation/mask enum members are **Chinese identifiers** — use exactly: fade-in `IntroType.渐显`, fade-out `OutroType.渐隐`, text fade-in `TextIntro.渐显`, text fade-out `TextOutro.渐隐`, rectangle mask `MaskType.矩形`. `TextStyle.color` is an RGB tuple in `[0,1]`; `TextBackground.color` is `"#RRGGBB"`; `add_background_filling(color=...)` is `"#RRGGBBAA"`.
- **Aesthetic guardrails:** dark-tech/liquid-glass, talking-head is hero, overlays in negative space off the face, line-level subtitle emphasis (no per-word coloring in v1), elegant short animations only.
- **Deferred (do NOT build in v1):** per-word subtitle highlight, true two-source split, Lottie/Remotion animated MG, true blur-behind-video glass.

---

## File Structure

| File | Responsibility |
|---|---|
| `finishing/__init__.py` | Package marker |
| `finishing/config.py` | Paths (drafts root, assets, style_ref), layout constants, palette, guardrails |
| `finishing/timemap.py` | EDL source→final mapping; emit enriched `transcript_final.json` |
| `finishing/style.py` | Hex→RGB helpers, subtitle/overlay `TextStyle`/`TextBackground` factories, font resolution |
| `finishing/beats.py` | `Beat`/manifest load + schema validation + bounds checks against timeline |
| `finishing/templates/*.html` | Glassmorphism HTML/CSS templates (key_point_card, side_card, bottom_banner, floating_label, end_screen, lower_third) |
| `finishing/assets_gen.py` | Playwright render templates → transparent PNG; ffmpeg style_ref frame sampling |
| `finishing/build_finish.py` | pycapcut assembly: base track, subtitles, overlays, punch-ins, pseudo-split, end-screen, outro, versioned naming |
| `finishing/pipeline.py` | Orchestrator + CLI: `--prep` (emit enriched transcript + manifest skeleton) and build phases; review summary; CapCut-closed check |
| `finishing/prompts/*.md` | The 8 canonical planner prompts (2–9) |
| `.claude/commands/capcut-finishing-editor.md` | The skill/command that orchestrates the run with the review gate |
| `tests/finishing/*.py` | Unit/integration tests |

**Data contracts (used across tasks):**

`jobs/<job>/transcript_final.json` (emitted by timemap; consumed by Claude):
```json
{"source": "...", "fps": 30, "width": 1920, "height": 1080,
 "final_duration": 58.2,
 "words": [{"i": 0, "src_start": 10.0, "src_end": 10.4,
            "final_start": 0.0, "final_end": 0.4, "text": "para"}]}
```

`jobs/<job>/finishing_manifest.json` (written by Claude; consumed by assets_gen + build):
```json
{"job": "myvideo", "beats": [
  {"id": 1, "type": "hook", "treatment": "subtitle+punch_in",
   "final_in": 0.0, "final_out": 4.2, "src_in": 10.0, "src_out": 14.2,
   "spoken": "exact phrase", "reason": "opening hook",
   "text": "Build faster with AI", "placement": "lower_third",
   "anim_in": "fade", "anim_out": "fade", "glass": true,
   "punch_in": 1.12, "subtitle_emphasis": false, "reposition_overlays": false,
   "accent": null}
]}
```
`treatment` ∈ `subtitle_only | subtitle+punch_in | left_card | right_card | bottom_banner | floating_label | pseudo_split | end_screen`.

---

### Task 1: Time mapping (`finishing/timemap.py`)

Pure functions: given an EDL (rough-cut keep ranges) plus optional intro/outro durations, map any source-time to final-timeline-time, and emit an enriched transcript whose words carry both.

**Files:**
- Create: `finishing/__init__.py` (empty)
- Create: `finishing/timemap.py`
- Test: `tests/finishing/test_timemap.py`

**Interfaces:**
- Produces:
  - `build_segments(edl: dict, intro_dur: float = 0.0) -> list[dict]` → `[{"src_start","src_end","final_start","final_end"}]` (kept ranges laid end-to-end; intro offsets the first final_start).
  - `src_to_final(t: float, segments: list[dict]) -> float | None` → final time for a source time inside a kept range, else `None` (time was cut).
  - `enrich_transcript(transcript: dict, edl: dict, intro_dur: float = 0.0) -> dict` → enriched dict per the `transcript_final.json` contract (drops words fully inside cuts).

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_timemap.py
from finishing.timemap import build_segments, src_to_final, enrich_transcript

EDL = {"source": "c.mp4", "fps": 30, "width": 1920, "height": 1080,
       "keep": [{"start": 10.0, "end": 13.0}, {"start": 20.0, "end": 22.0}]}

def test_segments_lay_end_to_end():
    segs = build_segments(EDL)
    assert segs[0] == {"src_start": 10.0, "src_end": 13.0, "final_start": 0.0, "final_end": 3.0}
    assert segs[1] == {"src_start": 20.0, "src_end": 22.0, "final_start": 3.0, "final_end": 5.0}

def test_segments_with_intro_offset():
    segs = build_segments(EDL, intro_dur=2.0)
    assert segs[0]["final_start"] == 2.0

def test_src_to_final_inside_and_cut():
    segs = build_segments(EDL)
    assert src_to_final(21.0, segs) == 4.0      # 3.0 + (21-20)
    assert src_to_final(15.0, segs) is None      # falls in a cut

def test_enrich_drops_cut_words():
    t = {"source": "c.mp4", "fps": 30.0, "width": 1920, "height": 1080,
         "words": [{"i": 0, "start": 11.0, "end": 11.5, "text": "kept"},
                   {"i": 1, "start": 15.0, "end": 15.5, "text": "cut"}]}
    out = enrich_transcript(t, EDL)
    assert [w["text"] for w in out["words"]] == ["kept"]
    assert out["words"][0]["final_start"] == 1.0
    assert out["final_duration"] == 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_timemap.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'finishing'`.

- [ ] **Step 3: Write minimal implementation**

```python
# finishing/__init__.py
"""CapCut Finishing Editor (CFE) engine."""
```

```python
# finishing/timemap.py
"""Map rough-cut source time -> final-timeline time, and enrich the transcript.

The rough cut lays kept ranges end-to-end (optionally after an intro clip).
A source time inside a kept range has a final-timeline position; a source time
inside a cut has none. All times are SECONDS (floats)."""
from __future__ import annotations


def build_segments(edl: dict, intro_dur: float = 0.0) -> list[dict]:
    segs: list[dict] = []
    cursor = float(intro_dur)
    for r in edl["keep"]:
        s, e = float(r["start"]), float(r["end"])
        dur = e - s
        if dur <= 0:
            continue
        segs.append({"src_start": s, "src_end": e,
                     "final_start": cursor, "final_end": cursor + dur})
        cursor += dur
    return segs


def src_to_final(t: float, segments: list[dict]) -> float | None:
    for seg in segments:
        if seg["src_start"] <= t <= seg["src_end"]:
            return seg["final_start"] + (t - seg["src_start"])
    return None


def enrich_transcript(transcript: dict, edl: dict, intro_dur: float = 0.0) -> dict:
    segs = build_segments(edl, intro_dur=intro_dur)
    final_duration = segs[-1]["final_end"] if segs else 0.0
    words_out = []
    for w in transcript["words"]:
        fs = src_to_final(float(w["start"]), segs)
        fe = src_to_final(float(w["end"]), segs)
        if fs is None or fe is None:
            continue  # word fell inside a cut
        words_out.append({"i": w["i"], "src_start": w["start"], "src_end": w["end"],
                          "final_start": round(fs, 3), "final_end": round(fe, 3),
                          "text": w["text"]})
    return {"source": transcript["source"], "fps": transcript.get("fps", 30),
            "width": transcript.get("width", 1920), "height": transcript.get("height", 1080),
            "final_duration": round(final_duration, 3), "words": words_out}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_timemap.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add finishing/__init__.py finishing/timemap.py tests/finishing/test_timemap.py
git commit -m "feat(finishing): source->final time mapping + enriched transcript"
```

---

### Task 2: Config, palette & style factories (`finishing/config.py`, `finishing/style.py`)

Central constants (paths, layout positions, palette, guardrails) and pure helpers that turn the palette into pycapcut style objects.

**Files:**
- Create: `finishing/config.py`
- Create: `finishing/style.py`
- Test: `tests/finishing/test_style.py`

**Interfaces:**
- `finishing/config.py` produces module constants: `DRAFTS_ROOT`, `STYLE_REF_DIR`, `ACCENT_HEX`, `GLASS_BASE_HEX`, `LAYOUT` (dict of placement → `(transform_x, transform_y, scale)`), `STYLE_GUARDRAILS` (str), `OUTRO_PATH`.
- `finishing/style.py` produces:
  - `hex_to_rgb01(hex_str: str) -> tuple[float, float, float]`
  - `subtitle_style(emphasis: bool, accent_hex: str) -> "TextStyle"`
  - `subtitle_background() -> "TextBackground"`
  - `resolve_font(name: str) -> "FontType | None"` (returns the matching `FontType` member or `None` to use system default).

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_style.py
from finishing.style import hex_to_rgb01, subtitle_style, subtitle_background, resolve_font

def test_hex_to_rgb01():
    assert hex_to_rgb01("#FFFFFF") == (1.0, 1.0, 1.0)
    assert hex_to_rgb01("#000000") == (0.0, 0.0, 0.0)
    r, g, b = hex_to_rgb01("#22D3EE")
    assert abs(r - 34/255) < 1e-6 and abs(g - 211/255) < 1e-6 and abs(b - 238/255) < 1e-6

def test_subtitle_style_emphasis_is_larger_and_accented():
    base = subtitle_style(False, "#22D3EE")
    emph = subtitle_style(True, "#22D3EE")
    assert emph.size > base.size
    assert base.color == (1.0, 1.0, 1.0)
    assert emph.color == hex_to_rgb01("#22D3EE")
    assert base.align == 1  # centered

def test_subtitle_background_is_rounded_translucent():
    bg = subtitle_background()
    assert bg.round_radius > 0
    assert 0.0 < bg.alpha < 1.0

def test_resolve_font_known_and_unknown():
    assert resolve_font("Montserrat") is not None
    assert resolve_font("NoSuchFont___") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_style.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'finishing.style'`.

- [ ] **Step 3: Write minimal implementation**

```python
# finishing/config.py
"""Paths, layout, palette and guardrails for the CFE engine."""
from __future__ import annotations
import os

# Reuse roughcut's CapCut drafts root and outro so branding stays consistent.
from roughcut.build_draft import DEFAULT_DRAFTS_ROOT as DRAFTS_ROOT  # noqa: F401
from roughcut.config import OUTRO_PATH, ASSETS_DIR  # noqa: F401

STYLE_REF_DIR = os.path.join(ASSETS_DIR, "style_ref")

# --- Palette (dark-tech / liquid-glass) -------------------------------------
ACCENT_HEX = "#22D3EE"      # electric cyan (override via --accent)
ACCENT_ALT_HEX = "#F5A623"  # warm alternate
GLASS_BASE_HEX = "#0B0F14"  # near-black glass base

# --- Layout: placement -> (transform_x, transform_y, scale) in half-canvas --
# transform_x: +right / -left; transform_y: +up / -down (1.0 == canvas edge).
LAYOUT = {
    "lower_third":      (0.0, -0.72, 1.0),
    "lower_third_up":   (0.0, -0.55, 1.0),   # nudged up when a banner is active
    "left_card":        (-0.45, 0.10, 1.0),
    "right_card":       (0.45, 0.10, 1.0),
    "bottom_banner":    (0.0, -0.80, 1.0),
    "floating_label":   (0.40, 0.45, 1.0),
    # pseudo-split: speaker pushed left & shrunk; card fills the right.
    "pseudo_speaker":   (-0.40, 0.0, 0.66),
    "pseudo_card":      (0.42, 0.0, 1.0),
    # end-screen: speaker masked frame left; text card right.
    "end_speaker":      (-0.42, 0.0, 1.0),
    "end_card":         (0.40, 0.0, 1.0),
}

STYLE_GUARDRAILS = (
    "Use graphics sparingly; keep the speaker as the hero; place overlays in "
    "negative space and never over the face; prioritize readability over "
    "decoration; premium UI glass cards, not stickers; subtle shadow/blur/"
    "rounded corners; avoid hyperactive transitions; emphasize key ideas, not "
    "every sentence; clean subtitle rhythm; end with a composed final frame."
)
```

```python
# finishing/style.py
"""Pure helpers turning the palette into pycapcut style objects."""
from __future__ import annotations

from . import config


def hex_to_rgb01(hex_str: str) -> tuple[float, float, float]:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def subtitle_style(emphasis: bool, accent_hex: str):
    from pycapcut import TextStyle
    return TextStyle(
        size=9.0 if emphasis else 7.0,
        bold=emphasis,
        color=hex_to_rgb01(accent_hex) if emphasis else (1.0, 1.0, 1.0),
        align=1,                 # centered
        auto_wrapping=True,
        max_line_width=0.74,     # keep to 1-2 lines, lower-third safe width
    )


def subtitle_background():
    from pycapcut import TextBackground
    # Rounded translucent near-black bar behind the caption for readability.
    return TextBackground(color=config.GLASS_BASE_HEX, alpha=0.55,
                          round_radius=0.3, height=0.16, width=0.78)


def resolve_font(name: str):
    """Return the matching FontType member, or None to use the system default."""
    from pycapcut import FontType
    try:
        return getattr(FontType, name)
    except AttributeError:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_style.py -v`
Expected: PASS (4 tests). (Imports `pycapcut`, already installed in the venv.)

- [ ] **Step 5: Commit**

```bash
git add finishing/config.py finishing/style.py tests/finishing/test_style.py
git commit -m "feat(finishing): config, palette, and pycapcut style factories"
```

---

### Task 3: Manifest schema & validation (`finishing/beats.py`)

Load `finishing_manifest.json`, validate every beat against the schema and the timeline bounds, and normalize defaults — so the build never sees a malformed beat.

**Files:**
- Create: `finishing/beats.py`
- Test: `tests/finishing/test_beats.py`

**Interfaces:**
- Consumes: `final_duration` (float) from the enriched transcript.
- Produces:
  - `TREATMENTS: frozenset[str]` and `PLACEMENTS: frozenset[str]`.
  - `load_manifest(path: str) -> dict` (raw JSON load).
  - `validate(manifest: dict, final_duration: float) -> list[str]` → list of human-readable error strings (empty = valid).
  - `normalize(manifest: dict) -> dict` → fills optional fields (`glass=True`, `punch_in=None`, `subtitle_emphasis=False`, `reposition_overlays=False`, `accent=None`) and sorts beats by `final_in`.

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_beats.py
import json
from finishing.beats import validate, normalize, TREATMENTS

def _beat(**kw):
    b = {"id": 1, "type": "hook", "treatment": "subtitle_only",
         "final_in": 0.0, "final_out": 2.0, "text": "hi"}
    b.update(kw)
    return b

def test_valid_manifest_has_no_errors():
    m = {"job": "x", "beats": [_beat()]}
    assert validate(m, final_duration=10.0) == []

def test_bad_treatment_flagged():
    m = {"job": "x", "beats": [_beat(treatment="explode")]}
    errs = validate(m, final_duration=10.0)
    assert any("treatment" in e for e in errs)

def test_out_of_bounds_flagged():
    m = {"job": "x", "beats": [_beat(final_out=99.0)]}
    errs = validate(m, final_duration=10.0)
    assert any("bounds" in e for e in errs)

def test_inverted_range_flagged():
    m = {"job": "x", "beats": [_beat(final_in=5.0, final_out=4.0)]}
    assert any("range" in e for e in validate(m, final_duration=10.0))

def test_normalize_fills_defaults_and_sorts():
    m = {"job": "x", "beats": [_beat(id=2, final_in=5.0, final_out=6.0),
                               _beat(id=1, final_in=0.0, final_out=1.0)]}
    out = normalize(m)
    assert [b["id"] for b in out["beats"]] == [1, 2]
    assert out["beats"][0]["glass"] is True
    assert out["beats"][0]["punch_in"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_beats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'finishing.beats'`.

- [ ] **Step 3: Write minimal implementation**

```python
# finishing/beats.py
"""Load, validate and normalize the Claude-authored finishing manifest."""
from __future__ import annotations
import json

TREATMENTS = frozenset({
    "subtitle_only", "subtitle+punch_in", "left_card", "right_card",
    "bottom_banner", "floating_label", "pseudo_split", "end_screen",
})
PLACEMENTS = frozenset({
    "lower_third", "left_card", "right_card", "bottom_banner",
    "floating_label", "center",
})
_REQUIRED = ("id", "type", "treatment", "final_in", "final_out")


def load_manifest(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(manifest: dict, final_duration: float) -> list[str]:
    errs: list[str] = []
    beats = manifest.get("beats")
    if not isinstance(beats, list) or not beats:
        return ["manifest has no beats"]
    for b in beats:
        tag = f"beat {b.get('id', '?')}"
        for k in _REQUIRED:
            if k not in b:
                errs.append(f"{tag}: missing required field '{k}'")
        if b.get("treatment") not in TREATMENTS:
            errs.append(f"{tag}: invalid treatment '{b.get('treatment')}'")
        fi, fo = b.get("final_in"), b.get("final_out")
        if isinstance(fi, (int, float)) and isinstance(fo, (int, float)):
            if fo <= fi:
                errs.append(f"{tag}: inverted/zero range ({fi} -> {fo})")
            if fi < 0 or fo > final_duration + 0.05:
                errs.append(f"{tag}: out of bounds (0..{final_duration})")
    return errs


def normalize(manifest: dict) -> dict:
    out = {"job": manifest.get("job", ""), "beats": []}
    for b in manifest["beats"]:
        nb = dict(b)
        nb.setdefault("glass", True)
        nb.setdefault("punch_in", None)
        nb.setdefault("subtitle_emphasis", False)
        nb.setdefault("reposition_overlays", False)
        nb.setdefault("accent", None)
        nb.setdefault("anim_in", "fade")
        nb.setdefault("anim_out", "fade")
        nb.setdefault("text", "")
        nb.setdefault("placement", "lower_third")
        out["beats"].append(nb)
    out["beats"].sort(key=lambda x: x["final_in"])
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_beats.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add finishing/beats.py tests/finishing/test_beats.py
git commit -m "feat(finishing): manifest schema validation and normalization"
```

---

### Task 4: Glass-card asset generation (`finishing/templates/*.html`, `finishing/assets_gen.py`)

Render premium glassmorphism cards to transparent PNGs from HTML/CSS via Playwright, and sample frames from style-ref videos via ffmpeg.

**Files:**
- Create: `finishing/templates/card.html` (one parametric template covers key_point/side/banner/label/end via query params)
- Create: `finishing/assets_gen.py`
- Test: `tests/finishing/test_assets_gen.py`

**Interfaces:**
- Produces:
  - `render_card(out_png: str, *, title: str, subtitle: str = "", accent_hex: str, kind: str = "side_card", width: int = 900, height: int = 360) -> str` → writes a transparent PNG, returns its path.
  - `sample_style_ref(style_ref_dir: str, out_dir: str, per_video: int = 3) -> list[str]` → extract frames (jpg) from each video via ffmpeg; returns frame paths.

**Setup note (fold into this task):** Playwright Chromium must be installed once: `./.venv/Scripts/python.exe -m playwright install chromium`. Add `playwright` to `requirements.txt`.

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_assets_gen.py
import os
from PIL import Image
from finishing.assets_gen import render_card

def test_render_card_produces_transparent_png(tmp_path):
    out = str(tmp_path / "card.png")
    render_card(out, title="Key Point", subtitle="automation", accent_hex="#22D3EE",
                kind="side_card", width=600, height=300)
    assert os.path.exists(out)
    img = Image.open(out)
    assert img.mode == "RGBA"
    assert img.size == (600, 300)
    # Has at least one fully transparent pixel (corner) -> background is transparent.
    assert img.getpixel((0, 0))[3] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_assets_gen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'finishing.assets_gen'`.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- finishing/templates/card.html -->
<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{margin:0;background:transparent;}
  *{box-sizing:border-box;font-family:'Segoe UI',Arial,sans-serif;}
  .wrap{display:flex;align-items:center;justify-content:flex-start;
        width:100vw;height:100vh;padding:28px;}
  .card{position:relative;width:100%;padding:28px 32px;border-radius:22px;
        background:rgba(11,15,20,0.72);
        border:1px solid rgba(255,255,255,0.14);
        box-shadow:0 18px 50px rgba(0,0,0,0.45),
                   inset 0 1px 0 rgba(255,255,255,0.12);
        backdrop-filter:blur(8px);}
  .tag{display:inline-block;font-size:18px;font-weight:600;letter-spacing:.12em;
       text-transform:uppercase;color:var(--accent);margin-bottom:10px;}
  .title{font-size:46px;font-weight:700;color:#F2F6FA;line-height:1.1;}
  .sub{margin-top:10px;font-size:26px;color:#9FB0BF;}
  .bar{position:absolute;left:0;top:18px;bottom:18px;width:5px;border-radius:4px;
       background:var(--accent);}
</style></head><body>
  <div class="wrap"><div class="card">
    <div class="bar"></div>
    <div class="tag" id="tag"></div>
    <div class="title" id="title"></div>
    <div class="sub" id="sub"></div>
  </div></div>
<script>
  const p = new URLSearchParams(location.search);
  document.documentElement.style.setProperty('--accent', p.get('accent') || '#22D3EE');
  const tag = p.get('tag') || '';
  document.getElementById('tag').textContent = tag;
  document.getElementById('tag').style.display = tag ? 'inline-block' : 'none';
  document.getElementById('title').textContent = p.get('title') || '';
  const sub = p.get('sub') || '';
  document.getElementById('sub').textContent = sub;
  document.getElementById('sub').style.display = sub ? 'block' : 'none';
</script></body></html>
```

```python
# finishing/assets_gen.py
"""Render glass-card PNGs (HTML/CSS via Playwright) and sample style-ref frames."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from urllib.parse import urlencode

_TEMPLATE = Path(__file__).resolve().parent / "templates" / "card.html"

# Tag shown above the title per card kind.
_TAGS = {"key_point_card": "Key Point", "side_card": "", "bottom_banner": "",
         "floating_label": "", "end_screen": "", "lower_third": ""}


def render_card(out_png: str, *, title: str, subtitle: str = "", accent_hex: str,
                kind: str = "side_card", width: int = 900, height: int = 360) -> str:
    from playwright.sync_api import sync_playwright
    params = {"title": title, "sub": subtitle, "accent": accent_hex,
              "tag": _TAGS.get(kind, "")}
    url = _TEMPLATE.as_uri() + "?" + urlencode(params)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height},
                                device_scale_factor=2)
        # Transparent background so the card composits cleanly over video.
        page.emulate_media(color_scheme="dark")
        page.goto(url)
        page.screenshot(path=out_png, omit_background=True)
        browser.close()
    return out_png


def sample_style_ref(style_ref_dir: str, out_dir: str, per_video: int = 3) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    frames: list[str] = []
    if not os.path.isdir(style_ref_dir):
        return frames
    vids = [p for p in Path(style_ref_dir).iterdir()
            if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")]
    for vid in vids:
        for n in range(per_video):
            # Sample at evenly spaced percentages (skip the very start/end).
            pct = (n + 1) / (per_video + 1)
            out = os.path.join(out_dir, f"{vid.stem}_{n}.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{pct*100:.0f}%", "-i", str(vid),
                 "-frames:v", "1", "-q:v", "3", out],
                check=False, capture_output=True)
            if os.path.exists(out):
                frames.append(out)
    return frames
```

Add to `requirements.txt`:
```
playwright>=1.40
```

- [ ] **Step 4: Install Chromium, then run test to verify it passes**

Run:
```bash
./.venv/Scripts/python.exe -m pip install playwright
./.venv/Scripts/python.exe -m playwright install chromium
./.venv/Scripts/python.exe -m pytest tests/finishing/test_assets_gen.py -v
```
Expected: PASS (1 test) — a 600×300 RGBA PNG with a transparent corner.

- [ ] **Step 5: Commit**

```bash
git add finishing/templates/card.html finishing/assets_gen.py tests/finishing/test_assets_gen.py requirements.txt
git commit -m "feat(finishing): glassmorphism PNG rendering + style-ref frame sampling"
```

---

### Task 5: Build base track + subtitles (`finishing/build_finish.py`)

Start the builder: lay the rough-cut keep ranges as base video segments, then add a subtitle text track from the manifest (lower-third, line-level emphasis, shift-up when a bottom banner overlaps). Verify by inspecting the saved draft JSON.

**Files:**
- Create: `finishing/build_finish.py`
- Test: `tests/finishing/test_build_subtitles.py`

**Interfaces:**
- Consumes: normalized manifest (Task 3), `LAYOUT`/palette (Task 2), `subtitle_style`/`subtitle_background` (Task 2), `build_segments` (Task 1).
- Produces:
  - `versioned_name(drafts_root: str, base: str) -> str` → `base` if free else `base_v2`, `base_v3`… (note: caller passes `<job>_(CFE Edit)_v1` as base; see Task 7).
  - `add_base_track(script, p, edl, mat_sec, intro_dur=0.0) -> list[dict]` → adds the base video track end-to-end; returns the segment list from `build_segments`.
  - `add_subtitles(script, p, manifest, accent_hex) -> None` → adds a text track; one `TextSegment` per beat that has `text`, positioned lower-third (or `lower_third_up` if a `bottom_banner` beat overlaps), fade in/out.
  - `build(edl, manifest, draft_name, *, drafts_root, accent_hex, outro_path=None) -> str` (stub that wires base + subtitles for now; extended in Tasks 6–7).

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_build_subtitles.py
import json
from pathlib import Path
from finishing.build_finish import build

EDL = {"source": None, "fps": 30, "width": 1280, "height": 720,
       "keep": [{"start": 0.0, "end": 5.0}, {"start": 6.0, "end": 10.0}]}

def _edl_with_video(tmp_path):
    # Make a tiny real clip so VideoMaterial can read its duration.
    import subprocess
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-t", "10", "-pix_fmt", "yuv420p", str(src)],
                   check=True, capture_output=True)
    e = dict(EDL); e["source"] = str(src); return e

def test_subtitles_written_to_draft(tmp_path):
    edl = _edl_with_video(tmp_path)
    manifest = {"job": "demo", "beats": [
        {"id": 1, "type": "hook", "treatment": "subtitle_only",
         "final_in": 0.5, "final_out": 3.0, "text": "Hello world",
         "placement": "lower_third", "glass": True, "punch_in": None,
         "subtitle_emphasis": False, "reposition_overlays": False,
         "anim_in": "fade", "anim_out": "fade", "accent": None}]}
    root = str(tmp_path / "drafts")
    path = build(edl, manifest, "demo_(CFE Edit)_v1", drafts_root=root, accent_hex="#22D3EE")
    data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
    texts = [m for m in data["materials"]["texts"]]
    assert any("Hello world" in (t.get("content") or "") for t in texts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_build_subtitles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'finishing.build_finish'`.

- [ ] **Step 3: Write minimal implementation**

```python
# finishing/build_finish.py
"""Assemble the polished CapCut draft from a rough-cut EDL + finishing manifest.

Only ever CREATES a new draft. CapCut must be CLOSED while writing.
Times: pycapcut treats bare numbers as microseconds; pass seconds as "1.5s"."""
from __future__ import annotations
from pathlib import Path

from . import config, beats
from .style import subtitle_style, subtitle_background
from .timemap import build_segments


def _secs(x: float) -> str:
    return f"{max(0.0, float(x)):.3f}s"


def versioned_name(drafts_root: str, base: str) -> str:
    root = Path(drafts_root)
    if not (root / base).exists():
        return base
    i = 2
    while (root / f"{base}_v{i}").exists():
        i += 1
    return f"{base}_v{i}"


def add_base_track(script, p, edl, mat_sec, intro_dur: float = 0.0):
    segs = build_segments(edl, intro_dur=intro_dur)
    mat = p.VideoMaterial(edl["source"])
    script.add_material(mat)
    script.add_track(p.TrackType.video, "base")
    for seg in segs:
        start = max(0.0, seg["src_start"])
        end = min(seg["src_end"], mat_sec)
        dur = end - start
        if dur <= 0.02:
            continue
        vs = p.VideoSegment(
            mat,
            p.trange(_secs(seg["final_start"]), _secs(dur)),
            source_timerange=p.trange(_secs(start), _secs(dur)),
        )
        script.add_segment(vs, track_name="base")
    return segs


def _banner_windows(manifest):
    return [(b["final_in"], b["final_out"]) for b in manifest["beats"]
            if b["treatment"] == "bottom_banner"]


def add_subtitles(script, p, manifest, accent_hex: str) -> None:
    script.add_track(p.TrackType.text, "subtitles")
    banners = _banner_windows(manifest)
    for b in manifest["beats"]:
        text = (b.get("text") or "").strip()
        if not text:
            continue
        fi, fo = float(b["final_in"]), float(b["final_out"])
        overlaps_banner = any(not (fo <= bs or fi >= be) for bs, be in banners)
        tx, ty, _ = config.LAYOUT["lower_third_up" if overlaps_banner else "lower_third"]
        seg = p.TextSegment(
            text, p.trange(_secs(fi), _secs(fo - fi)),
            style=subtitle_style(bool(b.get("subtitle_emphasis")), accent_hex),
            background=subtitle_background(),
            clip_settings=p.ClipSettings(transform_x=tx, transform_y=ty),
        )
        seg.add_animation(p.TextIntro.渐显, "0.4s")
        seg.add_animation(p.TextOutro.渐隐, "0.4s")
        script.add_segment(seg, track_name="subtitles")


def build(edl, manifest, draft_name, *, drafts_root, accent_hex,
          outro_path=None) -> str:
    import pycapcut as p
    manifest = beats.normalize(manifest)

    w = int(edl.get("width") or 1920)
    h = int(edl.get("height") or 1080)
    fps = int(round(float(edl.get("fps") or 30)))

    Path(drafts_root).mkdir(parents=True, exist_ok=True)
    name = versioned_name(drafts_root, draft_name)
    df = p.DraftFolder(drafts_root)
    script = df.create_draft(name, w, h, fps=fps)

    mat_sec = p.VideoMaterial(edl["source"]).duration / 1_000_000.0
    add_base_track(script, p, edl, mat_sec)
    add_subtitles(script, p, manifest, accent_hex)

    script.save()
    return str(Path(drafts_root) / name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_build_subtitles.py -v`
Expected: PASS (1 test) — draft JSON contains a text material with "Hello world".

- [ ] **Step 5: Commit**

```bash
git add finishing/build_finish.py tests/finishing/test_build_subtitles.py
git commit -m "feat(finishing): build base video track + lower-third subtitles"
```

---

### Task 6: Overlays, punch-ins & pseudo-split (`finishing/build_finish.py`)

Extend the builder: an overlay video track that places rendered glass-card PNGs in negative space (left/right/banner/label and the pseudo-split card), full-frame punch-ins via keyframes (clipped per base segment), and the pseudo-split speaker reframe.

**Files:**
- Modify: `finishing/build_finish.py`
- Test: `tests/finishing/test_build_overlays.py`

**Interfaces:**
- Consumes: `render_card` (Task 4), `add_base_track` return value (segment list), `LAYOUT` (Task 2).
- Produces:
  - `add_overlays(script, p, manifest, segs, assets_dir, accent_hex) -> None` → adds an `"overlay"` video track; for each card-bearing beat renders a PNG (if not present) and places it at its `LAYOUT` position with fade in/out.
  - `apply_punch_ins(p, base_segments_objs, manifest) -> None` → for each `subtitle+punch_in` beat (and any beat with numeric `punch_in`), add `uniform_scale` keyframes (1.0 → value → 1.0) on the overlapping base segment(s), clipped to segment boundaries; skip beats whose treatment is `pseudo_split`.
  - `apply_pseudo_split(p, base_segments_objs, segs, manifest) -> None` → for each `pseudo_split` beat, keyframe the overlapping base segment's `position_x`/`uniform_scale` to the `pseudo_speaker` layout for the beat window.
- Refactor `add_base_track` to also return the created `VideoSegment` objects (so keyframes can be attached): change its return to `(segs, seg_objs)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_build_overlays.py
import json, subprocess
from pathlib import Path
from finishing.build_finish import build

def _edl(tmp_path):
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-t", "10", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    return {"source": str(src), "fps": 30, "width": 1280, "height": 720,
            "keep": [{"start": 0.0, "end": 10.0}]}

def test_overlay_card_and_punchin(tmp_path):
    edl = _edl(tmp_path)
    manifest = {"job": "demo", "beats": [
        {"id": 1, "type": "tool", "treatment": "right_card", "final_in": 1.0,
         "final_out": 4.0, "text": "LangChain", "placement": "right_card",
         "glass": True, "punch_in": None, "anim_in": "fade", "anim_out": "fade",
         "subtitle_emphasis": False, "reposition_overlays": False, "accent": None},
        {"id": 2, "type": "benefit", "treatment": "subtitle+punch_in", "final_in": 5.0,
         "final_out": 7.0, "text": "Save hours", "placement": "lower_third",
         "glass": True, "punch_in": 1.12, "anim_in": "fade", "anim_out": "fade",
         "subtitle_emphasis": True, "reposition_overlays": False, "accent": None}]}
    root = str(tmp_path / "drafts")
    path = build(edl, manifest, "demo_(CFE Edit)_v1", drafts_root=root, accent_hex="#22D3EE")
    data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
    # An overlay image material exists (the rendered PNG), and base has keyframes.
    assert len(data["materials"].get("videos", [])) >= 2  # base clip + 1 overlay png
    base_track = next(t for t in data["tracks"] if t.get("name") == "base")
    seg = base_track["segments"][0]
    assert seg["common_keyframes"], "expected punch-in keyframes on base segment"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_build_overlays.py -v`
Expected: FAIL — base segment has no keyframes / no overlay material (functions not yet added).

- [ ] **Step 3: Write minimal implementation**

Modify `add_base_track` to collect segment objects and return them, and wire the new functions into `build`:

```python
# finishing/build_finish.py  — replace add_base_track and build; add new functions

import os

_PLACEMENT_KEY = {"left_card": "left_card", "right_card": "right_card",
                  "bottom_banner": "bottom_banner", "floating_label": "floating_label",
                  "pseudo_split": "pseudo_card"}
_CARD_KINDS = {"left_card": "side_card", "right_card": "side_card",
               "bottom_banner": "bottom_banner", "floating_label": "floating_label",
               "pseudo_split": "key_point_card"}


def add_base_track(script, p, edl, mat_sec, intro_dur: float = 0.0):
    segs = build_segments(edl, intro_dur=intro_dur)
    mat = p.VideoMaterial(edl["source"])
    script.add_material(mat)
    script.add_track(p.TrackType.video, "base")
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


def add_overlays(script, p, manifest, segs, assets_dir, accent_hex) -> None:
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
    """Return (idx, seg) for the base segment that contains the beat midpoint."""
    mid = (fi + fo) / 2.0
    for idx, s in enumerate(segs):
        if s["final_start"] <= mid <= s["final_end"] and seg_objs[idx] is not None:
            return idx, seg_objs[idx]
    return None, None


def apply_punch_ins(p, segs, seg_objs, manifest) -> None:
    for b in manifest["beats"]:
        if b["treatment"] == "pseudo_split":
            continue
        amt = b.get("punch_in")
        if not amt or b["treatment"] not in ("subtitle+punch_in",) and not isinstance(amt, (int, float)):
            continue
        if not isinstance(amt, (int, float)):
            continue
        fi, fo = float(b["final_in"]), float(b["final_out"])
        idx, seg = _overlapping_segment(segs, seg_objs, fi, fo)
        if seg is None:
            continue
        base = segs[idx]["final_start"]
        lo = max(0.0, fi - base)
        hi = min(segs[idx]["final_end"] - base, fo - base)
        seg.add_keyframe(p.KeyframeProperty.uniform_scale, _secs(lo), 1.0)
        seg.add_keyframe(p.KeyframeProperty.uniform_scale, _secs((lo + hi) / 2), float(amt))
        seg.add_keyframe(p.KeyframeProperty.uniform_scale, _secs(hi), 1.0)


def apply_pseudo_split(p, segs, seg_objs, manifest) -> None:
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
        for prop, target in ((p.KeyframeProperty.position_x, tx),
                             (p.KeyframeProperty.uniform_scale, sc)):
            seg.add_keyframe(prop, _secs(lo), 0.0 if prop == p.KeyframeProperty.position_x else 1.0)
            seg.add_keyframe(prop, _secs(lo + 0.4), target)
            seg.add_keyframe(prop, _secs(hi - 0.4), target)
            seg.add_keyframe(prop, _secs(hi), 0.0 if prop == p.KeyframeProperty.position_x else 1.0)


def build(edl, manifest, draft_name, *, drafts_root, accent_hex,
          outro_path=None, assets_dir=None) -> str:
    import pycapcut as p
    manifest = beats.normalize(manifest)
    w = int(edl.get("width") or 1920)
    h = int(edl.get("height") or 1080)
    fps = int(round(float(edl.get("fps") or 30)))
    Path(drafts_root).mkdir(parents=True, exist_ok=True)
    name = versioned_name(drafts_root, draft_name)
    df = p.DraftFolder(drafts_root)
    script = df.create_draft(name, w, h, fps=fps)
    mat_sec = p.VideoMaterial(edl["source"]).duration / 1_000_000.0

    segs, seg_objs = add_base_track(script, p, edl, mat_sec)
    assets_dir = assets_dir or str(Path(drafts_root).parent / "_cfe_assets" / name)
    add_overlays(script, p, manifest, segs, assets_dir, accent_hex)
    apply_punch_ins(p, segs, seg_objs, manifest)
    apply_pseudo_split(p, segs, seg_objs, manifest)
    add_subtitles(script, p, manifest, accent_hex)

    script.save()
    return str(Path(drafts_root) / name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_build_overlays.py tests/finishing/test_build_subtitles.py -v`
Expected: PASS (both tests — overlay material present, base segment has keyframes, subtitles still work).

- [ ] **Step 5: Commit**

```bash
git add finishing/build_finish.py tests/finishing/test_build_overlays.py
git commit -m "feat(finishing): glass overlays, punch-in keyframes, pseudo-split reframe"
```

---

### Task 7: End-screen, outro & versioned naming (`finishing/build_finish.py`)

Append a 4–6s end-screen (speaker reframed into a rounded rectangle mask on one side + a glass text card on the other), then the branded `outro.mp4`, and confirm the `(CFE Edit)_vN` versioning.

**Files:**
- Modify: `finishing/build_finish.py`
- Test: `tests/finishing/test_build_endscreen.py`

**Interfaces:**
- Consumes: `MaskType.矩形`, `render_card` (Task 4), `config.OUTRO_PATH`.
- Produces:
  - `add_end_screen(script, p, edl, segs, assets_dir, accent_hex, name_title=None, dur=5.0) -> float` → appends a masked speaker crop (last `dur`s of footage) + an end-card; returns the new timeline cursor (in seconds).
  - `add_full_clip(script, p, path, cursor) -> float` → append an entire clip (the outro) at `cursor`.
  - `build(...)` gains `do_end_screen: bool = True`, `name_title: str | None = None`; wires end-screen then outro after the base/overlay/subtitle layers.

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_build_endscreen.py
import json, subprocess
from pathlib import Path
from finishing.build_finish import build, versioned_name

def _edl(tmp_path):
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-t", "12", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    return {"source": str(src), "fps": 30, "width": 1280, "height": 720,
            "keep": [{"start": 0.0, "end": 12.0}]}

def test_endscreen_adds_masked_segment_and_versions(tmp_path):
    edl = _edl(tmp_path)
    manifest = {"job": "demo", "beats": [
        {"id": 1, "type": "cta", "treatment": "end_screen", "final_in": 11.0,
         "final_out": 12.0, "text": "Subscribe for more", "placement": "center",
         "glass": True, "punch_in": None, "anim_in": "fade", "anim_out": "fade",
         "subtitle_emphasis": False, "reposition_overlays": False, "accent": None}]}
    root = str(tmp_path / "drafts")
    p1 = build(edl, manifest, "demo_(CFE Edit)_v1", drafts_root=root,
               accent_hex="#22D3EE", name_title="Speaker|Founder")
    data = json.loads((Path(p1) / "draft_content.json").read_text(encoding="utf-8"))
    # A video segment carries a mask (the rounded speaker frame).
    masks = data["materials"].get("masks", [])
    assert masks, "expected a rounded rectangle mask for the end-screen crop"
    # Re-build versions to _v2 (folder already exists).
    assert versioned_name(root, "demo_(CFE Edit)_v1") == "demo_(CFE Edit)_v1_v2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_build_endscreen.py -v`
Expected: FAIL — no masks in the draft (end-screen not built yet).

- [ ] **Step 3: Write minimal implementation**

```python
# finishing/build_finish.py — add functions and extend build()

def add_full_clip(script, p, path, cursor: float) -> float:
    mat = p.VideoMaterial(path)
    script.add_material(mat)
    dur = mat.duration / 1_000_000.0
    seg = p.VideoSegment(mat, p.trange(_secs(cursor), _secs(dur)),
                         source_timerange=p.trange(_secs(0), _secs(dur)))
    script.add_segment(seg, track_name="base")
    return cursor + dur


def add_end_screen(script, p, edl, segs, assets_dir, accent_hex,
                   name_title=None, dur: float = 5.0) -> float:
    import os
    cursor = segs[-1]["final_end"] if segs else 0.0
    mat = p.VideoMaterial(edl["source"])
    mat_sec = mat.duration / 1_000_000.0
    tail_start = max(0.0, mat_sec - dur)
    real = min(dur, mat_sec)
    # Speaker crop: last `dur` seconds, masked to a rounded vertical frame, left.
    tx, _, _ = config.LAYOUT["end_speaker"]
    crop = p.VideoSegment(
        mat, p.trange(_secs(cursor), _secs(real)),
        source_timerange=p.trange(_secs(tail_start), _secs(real)),
        clip_settings=p.ClipSettings(transform_x=tx),
    )
    crop.add_mask(p.MaskType.矩形, size=0.9, round_corner=40.0,
                  rect_width=0.42)
    crop.add_animation(p.IntroType.渐显, "0.5s")
    script.add_segment(crop, track_name="base")
    # Text card on the opposite side.
    title = "Thanks for watching"
    subtitle = ""
    if name_title and "|" in name_title:
        title, subtitle = name_title.split("|", 1)
    from .assets_gen import render_card
    os.makedirs(assets_dir, exist_ok=True)
    png = os.path.join(assets_dir, "end_card.png")
    render_card(png, title=title, subtitle=subtitle, accent_hex=accent_hex,
                kind="end_screen", width=900, height=500)
    cmat = p.VideoMaterial(png)
    script.add_material(cmat)
    cx, cy, _ = config.LAYOUT["end_card"]
    card = p.VideoSegment(cmat, p.trange(_secs(cursor), _secs(real)),
                          clip_settings=p.ClipSettings(transform_x=cx, transform_y=cy))
    card.add_animation(p.IntroType.渐显, "0.5s")
    script.add_segment(card, track_name="overlay")
    return cursor + real


def build(edl, manifest, draft_name, *, drafts_root, accent_hex,
          outro_path=None, assets_dir=None, do_end_screen: bool = True,
          name_title=None) -> str:
    import pycapcut as p
    manifest = beats.normalize(manifest)
    w = int(edl.get("width") or 1920)
    h = int(edl.get("height") or 1080)
    fps = int(round(float(edl.get("fps") or 30)))
    Path(drafts_root).mkdir(parents=True, exist_ok=True)
    name = versioned_name(drafts_root, draft_name)
    df = p.DraftFolder(drafts_root)
    script = df.create_draft(name, w, h, fps=fps)
    mat_sec = p.VideoMaterial(edl["source"]).duration / 1_000_000.0

    segs, seg_objs = add_base_track(script, p, edl, mat_sec)
    assets_dir = assets_dir or str(Path(drafts_root).parent / "_cfe_assets" / name)
    add_overlays(script, p, manifest, segs, assets_dir, accent_hex)
    apply_punch_ins(p, segs, seg_objs, manifest)
    apply_pseudo_split(p, segs, seg_objs, manifest)
    add_subtitles(script, p, manifest, accent_hex)

    cursor = segs[-1]["final_end"] if segs else 0.0
    if do_end_screen:
        cursor = add_end_screen(script, p, edl, segs, assets_dir, accent_hex,
                                name_title=name_title)
    if outro_path and Path(outro_path).exists():
        add_full_clip(script, p, outro_path, cursor)

    script.save()
    return str(Path(drafts_root) / name)
```

> Note: if `add_mask` rejects `rect_width`, drop that kwarg — `size` + `round_corner` already give a rounded frame; `rect_width` only narrows it. The test asserts a mask exists, not its exact width.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/ -v`
Expected: PASS (all finishing tests — end-screen mask present, versioning increments).

- [ ] **Step 5: Commit**

```bash
git add finishing/build_finish.py tests/finishing/test_build_endscreen.py
git commit -m "feat(finishing): rounded-mask end-screen + outro + (CFE Edit) versioning"
```

---

### Task 8: Planner prompts (`finishing/prompts/`)

Persist the 8 canonical prompts as files so the skill injects them verbatim and they're versioned with the code.

**Files:**
- Create: `finishing/prompts/00_system.md` (role + STYLE_GUARDRAILS + the "never re-cut" boundary)
- Create: `finishing/prompts/01_beat_selection.md` (prompt 3)
- Create: `finishing/prompts/02_report.md` (prompt 2)
- Create: `finishing/prompts/03_manifest.md` (prompt 4 — defines the `finishing_manifest.json` schema)
- Create: `finishing/prompts/04_subtitles.md` (prompt 5)
- Create: `finishing/prompts/05_overlays.md` (prompt 6)
- Create: `finishing/prompts/06_punch_ins.md` (prompt 7)
- Create: `finishing/prompts/07_end_screen.md` (prompt 8)
- Test: `tests/finishing/test_prompts.py`

**Interfaces:**
- Produces: a `finishing/prompts/` directory whose files exist and are non-empty; `03_manifest.md` mentions every treatment in `beats.TREATMENTS`.

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_prompts.py
from pathlib import Path
from finishing.beats import TREATMENTS

PROMPTS = Path("finishing/prompts")

def test_all_prompt_files_present_and_nonempty():
    names = ["00_system", "01_beat_selection", "02_report", "03_manifest",
             "04_subtitles", "05_overlays", "06_punch_ins", "07_end_screen"]
    for n in names:
        f = PROMPTS / f"{n}.md"
        assert f.exists() and f.read_text(encoding="utf-8").strip()

def test_manifest_prompt_documents_every_treatment():
    txt = (PROMPTS / "03_manifest.md").read_text(encoding="utf-8")
    for t in TREATMENTS:
        assert t in txt, f"manifest prompt missing treatment '{t}'"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_prompts.py -v`
Expected: FAIL — prompt files don't exist.

- [ ] **Step 3: Write the prompt files**

Write each file using the user's finalized prompt text. For `03_manifest.md`, include the JSON schema from the Data Contracts section above and explicitly list all treatments. Example for `03_manifest.md` (others follow the same pattern, pasting the user's prompt 2/3/5/6/7/8 text verbatim):

````markdown
<!-- finishing/prompts/03_manifest.md -->
# Build manifest (prompt 4)

Turn the approved beat plan into `jobs/<job>/finishing_manifest.json`. Read
`jobs/<job>/transcript_final.json` and use the `final_start`/`final_end` fields
so all `final_in`/`final_out` values are in FINISHED-timeline seconds (also keep
the original `src_in`/`src_out` for traceability).

For each beat output: start/end timestamp (final + source), CapCut action,
on-screen text, placement, animation in/out, blur/shadow/glass/plain, punch-in,
and whether subtitles are standard or emphasized.

`treatment` MUST be one of:
`subtitle_only`, `subtitle+punch_in`, `left_card`, `right_card`,
`bottom_banner`, `floating_label`, `pseudo_split`, `end_screen`.

Schema:
```json
{"job": "<job>", "beats": [
  {"id": 1, "type": "hook", "treatment": "subtitle+punch_in",
   "final_in": 0.0, "final_out": 4.2, "src_in": 10.0, "src_out": 14.2,
   "spoken": "...", "reason": "...", "text": "On-screen copy",
   "placement": "lower_third", "anim_in": "fade", "anim_out": "fade",
   "glass": true, "punch_in": 1.12, "subtitle_emphasis": false,
   "reposition_overlays": false, "accent": null}
]}
```
Constraints: preserve speaker visibility, keep subtitles readable, avoid
covering the face, keep motion elegant and short. Do not add a beat for every
sentence — only the strongest moments.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_prompts.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add finishing/prompts/ tests/finishing/test_prompts.py
git commit -m "feat(finishing): canonical planner prompts (beat selection -> manifest)"
```

---

### Task 9: Pipeline orchestrator + CLI (`finishing/pipeline.py`)

Wire the deterministic stages and expose a CLI with two phases: `--prep` (emit `transcript_final.json` + a manifest skeleton, sample style-ref frames) and the default build phase (validate manifest → build draft). Include the CapCut-closed check and a review summary.

**Files:**
- Create: `finishing/pipeline.py`
- Test: `tests/finishing/test_pipeline.py`

**Interfaces:**
- Consumes: `enrich_transcript` (Task 1), `validate`/`load_manifest` (Task 3), `build` (Task 7), `sample_style_ref` (Task 4), `config`.
- Produces:
  - `prep(job: str) -> dict` → reads `jobs/<job>/transcript.json` + `edl.json`, writes `jobs/<job>/transcript_final.json` and a `finishing_manifest.skeleton.json`, samples style-ref frames to `jobs/<job>/style_frames/`. Returns paths + `final_duration`.
  - `run_build(job: str, *, accent_hex, name_title, do_end_screen, drafts_root=None) -> dict` → validates the manifest against `final_duration`; raises `ValueError` (joined error strings) if invalid; else builds `<job>_(CFE Edit)_v1` and returns `{"draft_path", "n_beats"}`.
  - `capcut_is_running() -> bool` (PowerShell `Get-Process CapCut`).
  - `main()` CLI.

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_pipeline.py
import json, subprocess
from pathlib import Path
import finishing.pipeline as pipe

def _job(tmp_path, monkeypatch):
    root = tmp_path / "jobs" / "demo"; root.mkdir(parents=True)
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                    "-t", "8", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    (root / "edl.json").write_text(json.dumps({
        "source": str(src), "fps": 30, "width": 640, "height": 360,
        "keep": [{"start": 0.0, "end": 8.0}]}), encoding="utf-8")
    (root / "transcript.json").write_text(json.dumps({
        "source": str(src), "fps": 30.0, "width": 640, "height": 360,
        "words": [{"i": 0, "start": 1.0, "end": 1.5, "text": "hi"}]}), encoding="utf-8")
    monkeypatch.setattr(pipe, "ROOT", tmp_path)
    return root

def test_prep_writes_enriched_transcript(tmp_path, monkeypatch):
    root = _job(tmp_path, monkeypatch)
    out = pipe.prep("demo")
    tf = json.loads((root / "transcript_final.json").read_text(encoding="utf-8"))
    assert tf["final_duration"] == 8.0
    assert out["final_duration"] == 8.0

def test_run_build_rejects_invalid_manifest(tmp_path, monkeypatch):
    root = _job(tmp_path, monkeypatch); pipe.prep("demo")
    (root / "finishing_manifest.json").write_text(json.dumps({
        "job": "demo", "beats": [{"id": 1, "type": "hook", "treatment": "BAD",
                                  "final_in": 0.0, "final_out": 2.0, "text": "x"}]}),
        encoding="utf-8")
    try:
        pipe.run_build("demo", accent_hex="#22D3EE", name_title=None,
                       do_end_screen=False, drafts_root=str(tmp_path / "drafts"))
        assert False, "should have raised"
    except ValueError as e:
        assert "treatment" in str(e)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'finishing.pipeline'`.

- [ ] **Step 3: Write minimal implementation**

```python
# finishing/pipeline.py
"""CFE orchestrator. Phase 1 (--prep): emit enriched transcript + manifest
skeleton + style frames for Claude. Phase 2 (default): validate the manifest
Claude wrote, then build the polished draft. CapCut must be CLOSED to build."""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

from . import config
from .timemap import enrich_transcript
from .assets_gen import sample_style_ref
from .beats import load_manifest, validate
from .build_finish import build

ROOT = Path(__file__).resolve().parent.parent


def _job_dir(job: str) -> Path:
    return ROOT / "jobs" / job


def prep(job: str) -> dict:
    jd = _job_dir(job)
    transcript = json.loads((jd / "transcript.json").read_text(encoding="utf-8"))
    edl = json.loads((jd / "edl.json").read_text(encoding="utf-8"))
    enriched = enrich_transcript(transcript, edl)
    (jd / "transcript_final.json").write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    # Manifest skeleton (Claude overwrites finishing_manifest.json).
    (jd / "finishing_manifest.skeleton.json").write_text(
        json.dumps({"job": job, "beats": []}, indent=2), encoding="utf-8")
    frames = sample_style_ref(config.STYLE_REF_DIR, str(jd / "style_frames"))
    print(f"[prep] {len(enriched['words'])} words, final_duration="
          f"{enriched['final_duration']}s, {len(frames)} style frames")
    return {"job_dir": str(jd), "final_duration": enriched["final_duration"],
            "style_frames": frames}


def run_build(job: str, *, accent_hex: str, name_title, do_end_screen: bool,
              drafts_root: str | None = None) -> dict:
    jd = _job_dir(job)
    edl = json.loads((jd / "edl.json").read_text(encoding="utf-8"))
    enriched = json.loads((jd / "transcript_final.json").read_text(encoding="utf-8"))
    manifest = load_manifest(str(jd / "finishing_manifest.json"))
    errs = validate(manifest, enriched["final_duration"])
    if errs:
        raise ValueError("invalid manifest:\n  - " + "\n  - ".join(errs))
    root = drafts_root or config.DRAFTS_ROOT
    outro = config.OUTRO_PATH if Path(config.OUTRO_PATH).exists() else None
    path = build(edl, manifest, f"{job}_(CFE Edit)_v1", drafts_root=root,
                 accent_hex=accent_hex, outro_path=outro,
                 do_end_screen=do_end_screen, name_title=name_title,
                 assets_dir=str(jd / "cfe_assets"))
    print(f"[build] draft -> {path}  ({len(manifest['beats'])} beats)")
    return {"draft_path": path, "n_beats": len(manifest["beats"])}


def capcut_is_running() -> bool:
    try:
        out = subprocess.run(
            ["powershell", "-c",
             "[bool](Get-Process CapCut -ErrorAction SilentlyContinue)"],
            capture_output=True, text=True, check=False)
        return out.stdout.strip().lower() == "true"
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="CapCut Finishing Editor pipeline")
    ap.add_argument("job", help="rough-cut job name under jobs/")
    ap.add_argument("--prep", action="store_true",
                    help="emit enriched transcript + manifest skeleton + style frames")
    ap.add_argument("--accent", default=config.ACCENT_HEX)
    ap.add_argument("--name-title", default=None, help='lower-third "Name|Title"')
    ap.add_argument("--no-endscreen", action="store_true")
    ap.add_argument("--drafts-root", default=None)
    a = ap.parse_args()
    if a.prep:
        prep(a.job)
        return
    if capcut_is_running():
        raise SystemExit("CapCut is running — close it before building the draft.")
    run_build(a.job, accent_hex=a.accent, name_title=a.name_title,
              do_end_screen=not a.no_endscreen, drafts_root=a.drafts_root)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_pipeline.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add finishing/pipeline.py tests/finishing/test_pipeline.py
git commit -m "feat(finishing): pipeline orchestrator + CLI (prep/build, manifest validation)"
```

---

### Task 10: The skill / command (`.claude/commands/capcut-finishing-editor.md`)

Author the orchestrating skill that runs the whole flow with the mandatory review gate, mirroring `roughcut.md`.

**Files:**
- Create: `.claude/commands/capcut-finishing-editor.md`
- Test: `tests/finishing/test_skill_doc.py`

**Interfaces:**
- Produces: a command doc that references the real CLI invocations and never skips the review gate or the CapCut-closed check.

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_skill_doc.py
from pathlib import Path

DOC = Path(".claude/commands/capcut-finishing-editor.md")

def test_skill_doc_covers_the_flow():
    assert DOC.exists()
    txt = DOC.read_text(encoding="utf-8").lower()
    for needle in ["--prep", "finishing_manifest.json", "review", "capcut",
                   "(cfe edit)", "-m finishing.pipeline"]:
        assert needle in txt, f"skill doc missing '{needle}'"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_skill_doc.py -v`
Expected: FAIL — the command doc doesn't exist.

- [ ] **Step 3: Write the command doc**

```markdown
<!-- .claude/commands/capcut-finishing-editor.md -->
You are the **CapCut Finishing Editor (CFE)**. You polish a COMPLETED rough-cut
job into a premium dark-tech / liquid-glass CapCut draft. You do NOT re-cut:
never remove words, filler, dead air, or change the rough-cut timing.

Engine runs in the venv: `./.venv/Scripts/python.exe -m finishing.pipeline ...`

## 1. Pick the job
`` is the rough-cut job name under `jobs/`. Confirm `jobs//transcript.json`
and `jobs//edl.json` exist (the rough cut must be done first via /roughcut).

## 2. Prep (deterministic)
Run:
```
./.venv/Scripts/python.exe -m finishing.pipeline  --prep
```
This writes `jobs//transcript_final.json` (words with final-timeline times),
a manifest skeleton, and `jobs//style_frames/*.jpg` sampled from
`assets/style_ref/`.

## 3. Plan the beats (you, Claude)
Read `finishing/prompts/00_system.md` then `01_beat_selection.md`, `02_report.md`,
`03_manifest.md`, `04_subtitles.md`, `05_overlays.md`, `06_punch_ins.md`,
`07_end_screen.md`. Look at the `style_frames` images to match the aesthetic.
Read `transcript_final.json` and select ONLY the strongest beats (hook, promise,
tool names, steps, comparisons, benefits, CTA). Then:
- Show the user the **report** (visual direction, beat-by-beat, subtitle guide,
  overlay plan, zoom/reframe plan, end-screen plan, editor notes, QC checklist).
- Write `jobs//finishing_manifest.json` per the schema in `03_manifest.md`
  (all `final_in/out` in finished-timeline seconds; treatments from the allowed set).

## 4. REVIEW GATE (do not skip)
Present the beat count + treatment breakdown and the report summary. Ask the
user to approve or request changes (fewer beats, different palette via `--accent`,
etc.). If changes: edit `finishing_manifest.json` and re-show. Only proceed on approval.

## 5. Build (CapCut must be CLOSED)
Check:
```
powershell -c "[bool](Get-Process CapCut -ErrorAction SilentlyContinue)"
```
If `True`, ask the user to close CapCut, then continue. Build:
```
./.venv/Scripts/python.exe -m finishing.pipeline  \
    --accent "#22D3EE" [--name-title "Name|Title"] [--no-endscreen]
```
This creates `_(CFE Edit)_v1` (auto-versions to `_v2`… on re-runs) in the
CapCut drafts folder, never touching the rough-cut draft. Tell the user to open
CapCut → the `_(CFE Edit)_vN` project shows subtitles + glass overlays +
punch-ins + end-screen, all still editable.

## Notes
- The build only CREATES drafts; it never edits existing ones.
- If the build reports an invalid manifest, fix the flagged beats and re-run.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_skill_doc.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/capcut-finishing-editor.md tests/finishing/test_skill_doc.py
git commit -m "feat(finishing): CapCut Finishing Editor skill/command with review gate"
```

---

### Task 11: End-to-end smoke test & docs

Prove the whole chain works on a tiny synthetic job and note the new system in the README.

**Files:**
- Create: `tests/finishing/test_e2e_smoke.py`
- Modify: `README.md` (add a "CapCut Finishing Editor" section)

**Interfaces:**
- Consumes: `prep`, `run_build` (Task 9).

- [ ] **Step 1: Write the failing test**

```python
# tests/finishing/test_e2e_smoke.py
import json, subprocess
from pathlib import Path
import finishing.pipeline as pipe

def test_full_chain(tmp_path, monkeypatch):
    jd = tmp_path / "jobs" / "smoke"; jd.mkdir(parents=True)
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                    "-t", "10", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    (jd / "edl.json").write_text(json.dumps({"source": str(src), "fps": 30,
        "width": 640, "height": 360, "keep": [{"start": 0.0, "end": 10.0}]}), encoding="utf-8")
    (jd / "transcript.json").write_text(json.dumps({"source": str(src), "fps": 30.0,
        "width": 640, "height": 360,
        "words": [{"i": 0, "start": 1.0, "end": 1.5, "text": "hi"}]}), encoding="utf-8")
    monkeypatch.setattr(pipe, "ROOT", tmp_path)
    pipe.prep("smoke")
    (jd / "finishing_manifest.json").write_text(json.dumps({"job": "smoke", "beats": [
        {"id": 1, "type": "hook", "treatment": "right_card", "final_in": 1.0,
         "final_out": 4.0, "text": "AI Skills", "placement": "right_card"},
        {"id": 2, "type": "cta", "treatment": "subtitle+punch_in", "final_in": 5.0,
         "final_out": 7.0, "text": "Subscribe", "punch_in": 1.1, "placement": "lower_third"}]}),
        encoding="utf-8")
    res = pipe.run_build("smoke", accent_hex="#22D3EE", name_title="Phil|Founder",
                         do_end_screen=True, drafts_root=str(tmp_path / "drafts"))
    assert Path(res["draft_path"]).exists()
    data = json.loads((Path(res["draft_path"]) / "draft_content.json").read_text(encoding="utf-8"))
    assert any(t.get("name") == "base" for t in data["tracks"])
    assert any(t.get("name") == "overlay" for t in data["tracks"])
    assert any(t.get("name") == "subtitles" for t in data["tracks"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/test_e2e_smoke.py -v`
Expected: FAIL initially only if any wiring is off; otherwise it confirms the chain. If it fails, fix the offending task before proceeding.

- [ ] **Step 3: Add the README section**

```markdown
## CapCut Finishing Editor (CFE)

After a rough cut is done, polish it into a premium dark-tech edit:

```
./.venv/Scripts/python.exe -m finishing.pipeline <job> --prep   # enrich transcript + style frames
# (Claude writes jobs/<job>/finishing_manifest.json, you review it)
./.venv/Scripts/python.exe -m finishing.pipeline <job>          # build (CLOSE CapCut first)
```

Produces a new `<job>_(CFE Edit)_v1` draft (subtitles, glass overlays, punch-ins,
pseudo-split, end-screen) — never touching the rough-cut draft. Use the
`/capcut-finishing-editor` command to run the full flow with a review gate.
```

- [ ] **Step 4: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/finishing/ -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add tests/finishing/test_e2e_smoke.py README.md
git commit -m "test(finishing): end-to-end smoke test + README section"
```

---

## Self-Review

**Spec coverage:**
- §2 architecture (engine + skill, deterministic + Claude manifest) → Tasks 9, 10.
- §3 inputs & source→final mapping, enriched transcript, style_ref frames, name/title, accent → Tasks 1, 4, 9.
- §4 beat planner (selection criteria, treatment vocabulary, guardrails, report + manifest) → Tasks 2 (guardrails), 8 (prompts), 3 (schema), 10 (skill drives report).
- §5 asset generation (HTML templates, Playwright PNG, palette, glass+blur) → Tasks 4, 2.
- §6 build (base track, subtitles w/ shift-up, overlays, punch-ins per-segment, pseudo-split, end-screen→outro, fonts, versioned naming) → Tasks 5, 6, 7.
- §7 review gate + CapCut-closed check → Tasks 9, 10.
- §8 skill args → Tasks 9, 10.
- §9 module breakdown → matches Tasks 1–10 file structure.
- §10 deferred items → none implemented (correct).

**Placeholder scan:** No "TBD/TODO" in steps; every code step shows complete code. The one conditional note (Task 7 `rect_width` fallback) is explicit, not a placeholder.

**Type consistency:** `build(...)` signature evolves across Tasks 5→6→7; the final signature (Task 7) is the one `pipeline.py` (Task 9) calls — `build(edl, manifest, draft_name, *, drafts_root, accent_hex, outro_path, assets_dir, do_end_screen, name_title)`. `add_base_track` returns `(segs, seg_objs)` from Task 6 onward; Tasks 6–7 consume both. `versioned_name`, `validate`, `normalize`, `enrich_transcript`, `render_card`, `sample_style_ref` names are consistent across consumers.

**Gaps fixed inline:** none outstanding.
