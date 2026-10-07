# CapCut Finishing Editor (CFE) — Design

**Date:** 2026-06-18
**Status:** Approved design, pre-implementation
**Relationship:** Second stage that runs *after* the existing rough-cut pipeline (`roughcut/`). It never re-cuts dialogue.

---

## 1. Purpose

Turn a cleaned, rough-cut talking-head video into a polished, premium "dark-tech / liquid-glass" YouTube-tutorial edit — automatically — by adding subtitles, glass-card overlays, punch-ins/reframes, pseudo-split layouts, and a composed end-screen into a **new, editable CapCut draft**. A human review gate sits before anything is built.

**Hard boundary:** The finishing editor starts *after* the rough cut. It does NOT remove filler/dead air/ums/retakes, does NOT re-cut dialogue, and does NOT remove words. Polish only.

---

## 2. Architecture & data flow

A new engine `finishing/` (sibling to `roughcut/`), run from the project venv, plus a skill/command `CapCut finishing editor.md` (parallel to `roughcut.md`).

```
roughcut job/  (transcript.json + edl.json + rough draft — all untouched)
        │
        ▼
[A] Beat planner (Claude)  → beat_plan.json + REPORT.md + finishing_manifest.json
        │
        ▼
[B] Asset generation (HTML/CSS templates → Playwright → transparent PNGs)
        │
        ▼   ── REVIEW GATE (report summary + beat breakdown; user approves) ──
        ▼
[C] Auto-build (pycapcut) → new "<job>_(CFE Edit)_v1" CapCut draft
```

Only ever **creates** a new draft; never edits the rough-cut draft or any existing draft.

---

## 3. Inputs & the time-mapping rule

- Reads the roughcut job's `transcript.json` (word-level, **source time**) and `edl.json` (keep ranges).
- Builds a **source → final-timeline map** from the EDL (kept segments are laid end-to-end; intro/outro offsets accounted for).
- Every beat carries **dual timestamps**: final-timeline (used by the build) **and** source/transcript (for traceability).
- Reads `assets/style_ref/` — ffmpeg extracts a few representative frames per reference video; the beat-planner reads those stills to match the aesthetic. Screenshots placed there are read directly. References are **optional** (templates carry the baseline look).
- Optional inputs: speaker **name/title** for the lower-third (skipped entirely if not provided); `--accent <hex>` to override the accent color.

---

## 4. Stage A — Beat planner (Claude semantic pass)

Selects **only the strongest beats** — never one per sentence. Eligible beat types (prompt 3): hook, promise/outcome, tool names, workflow steps, comparisons, important benefits, final CTA/wrap-up.

Each beat is assigned a treatment from the **unified vocabulary**:

```
subtitle_only | subtitle+punch_in | left_card | right_card |
bottom_banner | floating_label | pseudo_split | end_screen
```

Governed by a **`STYLE_GUARDRAILS`** constant (prompt 9) injected into the planner's reasoning: graphics sparingly, speaker is hero, overlays in negative space, readability over decoration, premium UI cards (not stickers), subtle shadow/blur/rounded corners, no hyperactive transitions, emphasize key ideas not every sentence, clean subtitle rhythm, composed final frame.

**Two artifacts emitted:**

1. **REPORT.md** — human-readable review doc (prompt 2 superset): overall visual direction, beat-by-beat timeline, subtitle style guide, overlay plan, zoom/crop/reframe plan, end-screen plan, editor notes — **plus** an appended QC checklist and an "assets to generate / drop in" list.
2. **`finishing_manifest.json`** — machine-readable per-beat build values (prompt 4): dual timestamps, action, on-screen text, placement, animation in/out, blur/shadow/glass/plain, punch-in flag, subtitle standard vs emphasized, color direction, off-face notes.

---

## 5. Stage B — Asset generation (HTML/CSS → transparent PNG)

**Toolchain:** real glassmorphism templates authored in HTML/CSS, rendered to transparent PNG via Playwright (headless Chromium). Claude fills the copy from the manifest.

**Template set:** `key_point_card`, `side_card`, `bottom_banner`, `floating_label`, `end_screen`, `lower_third`.

**Palette (default — overridable via `--accent`):**
- Glass base: near-black `#0B0F14` at ~70% opacity, subtle white border highlight, soft drop shadow, rounded corners, generous padding.
- Accent: electric cyan `#22D3EE` (warm alternate `#F5A623` available).
- Accent cues are informed by frames sampled from `assets/style_ref/`.

**Glass realization:** baked frosted PNG **plus** CapCut's native `add_background_filling("blur")` behind the card for depth.

---

## 6. Stage C — Auto-build (pycapcut) → `<job>_(CFE Edit)_v1`

**Track layout (bottom → top):**
- **V1 (base):** raw kept segments laid end-to-end (identical to the rough cut), then the **end-screen** composition, then the branded **`outro.mp4`** appended last.
- **V2 (overlays):** glass-card PNGs — left/right cards, bottom banners, floating labels — placed in negative space, never over the speaker's face.
- **T1 (subtitles):** lower-third, 1–2 lines, chunked on natural phrase boundaries, **line-level** emphasis (whole key line gets accent/glass treatment — no per-word coloring in v1). Subtitles **auto shift up** when a bottom banner is active so both stay readable.

**Behaviors:**
- **Punch-ins/reframes:** scale/position keyframes with eased interpolation, applied **per keep-segment** (a punch-in that would cross a hard cut is clipped to the segment boundary). Reserved for full-frame emphasis phrases; returns to base frame after.
- **Pseudo-split:** speaker reframed to one third via keyframes + a glass panel fills the freed negative space (no second video source required). Punch-ins are **not** stacked on pseudo-split beats.
- **End-screen (4–6s):** last ~4–6s of talking-head footage reframed into a **rounded rectangle mask** (vertical frame) on one side, text card + dark-tech glass background on the other; motion in/out via `add_animation`. Freeze-frame fallback if the tail is an awkward moment. Plays **before** the appended `outro.mp4`.
- **Fonts:** style guide names a target font; build resolves to an available CapCut font (`FontType`), falling back to default if absent.

**Output naming:** CapCut draft folder named `<job>_(CFE Edit)_v1`, auto-incrementing `_v2`, `_v3` on re-runs (always versioned, starting at v1). Any preview/export the finishing stage produces also carries the `(CFE Edit)` tag. Internal artifacts (beat_plan, manifest, report, PNGs) live under `jobs/<job>/`.

---

## 7. Review gate & safety

- After Stage A+B: show the REPORT summary + a beat-count/treatment breakdown + asset list, and **ask for approval**. The user can request changes (edit manifest, adjust palette/accent, fewer beats, etc.) and re-run.
- Before Stage C: **CapCut-closed check** (`Get-Process CapCut`) — same guard as roughcut (CapCut overwrites drafts from memory on exit; a new draft won't appear until restart). If open, ask the user to close it, then continue.
- The build only **creates** a new draft and auto-versions — never overwrites a draft the user may have already polished.

---

## 8. The skill — `CapCut finishing editor.md`

Mirrors the structure of `roughcut.md`:
1. Parse args (`<job>` name or video path; `--name`; `--accent <hex>`; `--name-title "Name|Title"`; `--no-endscreen`).
2. Run the beat planner (Stage A) → REPORT + manifest.
3. Generate assets (Stage B).
4. **Review gate** — show summary, wait for approval (do not skip).
5. CapCut-closed check.
6. Build the `<job>_(CFE Edit)_vN` draft (Stage C).
7. Tell the user to open CapCut → the new project shows subtitles + overlays + punch-ins + end-screen, all still editable/restorable.

---

## 9. Module breakdown

| File | Responsibility |
|---|---|
| `finishing/timemap.py` | EDL source→final timeline mapping; dual-timestamp helper |
| `finishing/beats.py` | Beat-plan I/O, manifest schema, validation |
| `finishing/style.py` | `STYLE_GUARDRAILS`, palette, font resolution |
| `finishing/templates/*.html` | Glassmorphism card/lower-third/banner/end-screen templates |
| `finishing/assets_gen.py` | Playwright render → transparent PNGs; style_ref frame sampling |
| `finishing/build_finish.py` | pycapcut assembly: subtitles, overlays, keyframes, masks, end-screen, outro |
| `finishing/pipeline.py` | Orchestrator + CLI |
| `finishing/prompts/` | The 8 canonical prompts (2–9) as the planner's instruction set |

---

## 10. Explicitly deferred (YAGNI for v1)

Designed so each can be added later without rework:
- **Per-word subtitle highlighting** (needs custom multi-range text JSON beyond pycapcut's API).
- **True two-source split** (needs supplied/tagged B-roll or screen recordings).
- **Lottie/Remotion animated motion graphics** (heavier toolchain).
- **True blur-behind-video glass** (duplicated/blurred/masked video layer).

---

## 11. Open data contracts (sketch)

`finishing_manifest.json`:
```json
{
  "job": "myvideo",
  "source": "C:/.../clip.mp4",
  "fps": 30, "width": 1920, "height": 1080,
  "beats": [
    {
      "id": 1,
      "type": "hook",
      "treatment": "subtitle+punch_in",
      "final_in": "00:00.0", "final_out": "00:04.2",
      "source_in": "00:12.4", "source_out": "00:16.6",
      "spoken": "exact phrase",
      "reason": "opening hook",
      "text": "on-screen copy",
      "placement": "lower_third",
      "anim_in": "fade", "anim_out": "fade",
      "glass": true, "punch_in": {"scale": 1.12, "ease": true},
      "subtitle_emphasis": false,
      "reposition_overlays": false
    }
  ]
}
```

(Schema finalized during implementation planning.)
