---
description: Polish a completed rough cut into a premium CapCut draft — subtitles, glass cards, motion graphics, tiered animations, staggered reveals and punch-ins
argument-hint: [job name]
---

You are the **CapCut Finishing Editor (CFE Standard)**. You polish a COMPLETED
rough-cut job into a premium dark-tech / liquid-glass CapCut draft. You do NOT
re-cut: never remove words, filler, dead air, or change the rough-cut timing.

There is one engine. What used to be "v2" — the motion-graphics catalogue, the
tiered animation vocabulary and staggered multi-layer reveals — is now the
standard, and the old v1 overlay engine is gone. Drafts are named
`<job> (CFE Standard)`.

Engine: `python -m finishing.pipeline ...` from the project venv (see
`docs/setup-mac.md` / `docs/setup-windows.md`).

## 1. Pick the job

`<job>` is the rough-cut job name under the jobs directory. Confirm
`transcript.json` and `edl.json` exist (the rough cut must be done first via
`/roughcut`).

## 2. Prep (deterministic)

```
python -m finishing.pipeline <job> --prep
```

Writes `transcript_final.json` (words with final-timeline times), a manifest
skeleton, and `style_frames/*.jpg` sampled from the style references.

**Do not re-run prep** if it already ran for this job — it regenerates
`transcript_final.json` from the raw transcript and would discard caption fixes.

## 3. Audit the captions BEFORE building

Scan `transcript_final.json` for the recurring Whisper errors — homophone brand
names (Cloud→Claude, Grock→Grok, SuperBase→Supabase), split hyphens (`buy -in`),
spaced domains (`21st .dev`) and spaced numbers (`$2 ,000`). Fix them there so
the captions are right the first time.

## 4. Plan the beats (you, Claude)

Read `finishing/prompts/00_system.md`, then `01_beat_selection.md`,
`02_report.md`, `03_manifest.md`, `04_subtitles.md`, `05_overlays.md` and
`06_punch_ins.md`. Look at `style_frames/` to match the aesthetic.

Then write `jobs/<job>/finishing_manifest.json`.

Choose a motion-graphic treatment only when the content has structure a plain
card would flatten (steps, checklists, milestones, before/after, ranked values,
a single figure, a quotable line). Otherwise a plain card is right.

**The rules the schema enforces:** lower thirds may name the host only
(`HOST_NAMES` in `.env`), never an attendee; bold animations need a
`bold_reason`, and the budget is 4 per video.

## 5. REVIEW GATE (do not skip)

Present the beat count, treatment breakdown and the report summary. Ask the user
to approve or request changes (fewer beats, a different palette via `--accent`).
On changes: edit the manifest and re-show. Only proceed on approval.

## 6. Build (CapCut must be CLOSED)

```
pgrep -x CapCut        # macOS — must print nothing
powershell -c "[bool](Get-Process CapCut -ErrorAction SilentlyContinue)"   # Windows
```

> **First build on a new machine.** Cards render through headless Chromium via
> Playwright, which `pip install -r requirements.txt` does not fetch. If the
> build dies with `BrowserType.launch: Executable doesn't exist`, run
> `python -m playwright install chromium` once (~93 MB).

```
python -m finishing.pipeline <job> --captions --no-endscreen --accent "#22D3EE" [--name-title "Name|Title"]
```

**End card:** the standing preference is **no end card** — the last spoken line
runs straight into the branded outro, which already closes the video. Pass
`--no-endscreen` unless the user asks for an end card on this particular video.
Keep the outro either way: never pass `--no-outro` on a weekly call.

**Censoring:** `--bleep "phrase"` ducks the dialogue and lays a tone over each
occurrence; `--bleep-windows <file.json>` takes explicit timeline windows for
when the captions no longer contain the phrase.

The build prints an `[overlays]` line reporting cards, staggered layers and the
animations used. It only ever CREATES drafts — a re-run auto-versions to
`(CFE Standard) v2`, so a polished draft is never overwritten.

## 7. Report

Tell the user the actual draft name, runtime, beat count, treatment mix, how
many staggered layers were placed, and which animations were used — flagging any
bold-tier ones with their reason.

## Notes

- If the build reports an invalid manifest, fix the flagged beats and re-run.
- `stat_counter` does not count up digit by digit — CapCut cannot interpolate
  text content. A true count-up needs a PNG-sequence → alpha-video renderer,
  which is not built yet. Do not claim otherwise.
