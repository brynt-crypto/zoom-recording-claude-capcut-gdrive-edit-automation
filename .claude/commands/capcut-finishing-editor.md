---
description: Polish a completed rough-cut into a premium dark-tech CapCut draft with beats, subtitles, overlays, and punch-ins
argument-hint: [job name]
---

You are the **CapCut Finishing Editor (CFE)**. You polish a COMPLETED rough-cut
job into a premium dark-tech / liquid-glass CapCut draft. You do NOT re-cut:
never remove words, filler, dead air, or change the rough-cut timing.

Engine runs in the venv: `./.venv/Scripts/python.exe -m finishing.pipeline ...`

## 1. Pick the job

`<job>` is the rough-cut job name under `jobs/`. Confirm `jobs/<job>/transcript.json`
and `jobs/<job>/edl.json` exist (the rough cut must be done first via /roughcut).

## 2. Prep (deterministic)

Run:
```
./.venv/Scripts/python.exe -m finishing.pipeline <job> --prep
```

This writes `jobs/<job>/transcript_final.json` (words with final-timeline times),
a manifest skeleton, and `jobs/<job>/style_frames/*.jpg` sampled from
`assets/style_ref/`.

## 3. Plan the beats (you, Claude)

Read `finishing/prompts/00_system.md` then `01_beat_selection.md`, `02_report.md`,
`03_manifest.md`, `04_subtitles.md`, `05_overlays.md`, `06_punch_ins.md`.
(Skip `07_end_screen.md` — see the no-end-card rule below.)
Look at the `style_frames` images to match the aesthetic.
Read `transcript_final.json` and select ONLY the strongest beats (hook, promise,
tool names, steps, comparisons, benefits, CTA). Then:
- Show the user the **report** (visual direction, beat-by-beat, subtitle guide,
  overlay plan, zoom/reframe plan, end-screen plan, editor notes, QC checklist).
- Write `jobs/<job>/finishing_manifest.json` per the schema in `03_manifest.md`
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

If `True`, ask the user to close CapCut, then continue.

> **First build on a new machine.** The overlay cards are rendered through headless
> Chromium via Playwright, which is NOT installed by `pip install -r requirements.txt`.
> If the build dies with `BrowserType.launch: Executable doesn't exist`, install it once:
> ```
> ./.venv-mac/bin/python -m playwright install chromium     # macOS
> ./.venv/Scripts/python.exe -m playwright install chromium # Windows
> ```
> ~93 MB, one time per machine. Then re-run the build. (Hit on macOS 2026-08-14.)

Build:
```
./.venv/Scripts/python.exe -m finishing.pipeline <job> \
    --no-endscreen --accent "#22D3EE" [--name-title "Name|Title"]
```

## ⛔ NO END CARD — always

`--no-endscreen` is **mandatory on every build**, and never author an `end_screen`
beat in `finishing_manifest.json`. The video must run straight from the last spoken
line into the branded `outro.mp4`, which already closes it — an end screen in front
of the outro is a redundant second ending. (Standing instruction, 2026-07-30.)
Keep the outro: use `--no-endscreen`, never `--no-outro`.

This creates `<job>_(CFE Edit)_v1` (auto-versions to `_v2`… on re-runs) in the
CapCut drafts folder, never touching the rough-cut draft. Tell the user to open
CapCut → the `<job>_(CFE Edit)_vN` project shows subtitles + glass overlays +
punch-ins + end-screen, all still editable.

## Notes

- The build only CREATES drafts; it never edits existing ones.
- If the build reports an invalid manifest, fix the flagged beats and re-run.
