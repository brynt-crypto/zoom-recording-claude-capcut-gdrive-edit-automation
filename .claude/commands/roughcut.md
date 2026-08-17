---
description: Auto rough-cut a video (remove silence/filler/stutters), add intro+outro, into an editable CapCut draft
argument-hint: [video path or name] [--longform] [--model medium|large-v3] [--safe] [--no-branding]
---

You are running the **rough-cut pipeline**. Turn a raw video into an editable
CapCut draft: dead air, filler, and stutters removed; brand intro + outro added.

Engine runs in the project venv: `./.venv/Scripts/python.exe -m roughcut.<module> ...`
Work the steps in order. **Never skip step 0 (file pick) or step 4 (brief + approval).**

> **macOS note.** On a Mac use `./.venv-mac/bin/python -m roughcut.<module> ...`
> and pass `--device cpu --compute int8` (Macs have no NVIDIA GPU; the code also
> auto-downgrades `cuda`→`cpu` on non-Windows, so it won't crash either way —
> just expect CPU-speed transcription on long files).

## 0. Choose the file (ALWAYS, unless an exact path is given and confirmed)
Run the discovery scan and show the user the list:
```
./.venv/Scripts/python.exe -m roughcut.discover --limit 25
```
- It lists the drop-folder `assets/to_edit/` first; if empty, it scans your
  configured video folders (newest first), with duration + size.
- Present the numbered list. If the user gave a name/description in `$ARGUMENTS`,
  point out the matching item but still confirm. Ask the user to pick a number
  (use AskUserQuestion with the top candidates if helpful).
- Resolve to one absolute path before continuing.

## 1. Parse options
`--model X` (default `medium`), `--device` (default `cuda`; fall back to `cpu` if
GPU errors), `--longform` (1h+; review in ~10-15 min windows), `--safe` (skip the
semantic pass), `--no-branding` (skip intro/outro). Job name = filename stem,
spaces→underscores.

## 1.5. ALWAYS ask about manual timestamps (before any cutting)
Ask the user (free text or AskUserQuestion):
- **Trim the start?** Remove everything before a timestamp (e.g. pre-roll/setup). → `--clip-start mm:ss`
- **Trim the end?** Remove everything after a timestamp. → `--clip-end mm:ss`
- **Remove specific parts?** Any mid ranges to delete (e.g. off-topic, a break). → `--exclude "12:30-15:00,40:00-41:10"`

Accept "none" for any. Timestamps may be `ss`, `mm:ss`, or `hh:mm:ss`. These are
applied as hard cuts alongside the automatic ones, and are shown in the brief.

## 2. Probe + 4. BRIEF, then WAIT FOR APPROVAL
Probe the file (`-m roughcut.discover` already shows duration, or ffprobe) and
present a **brief table** the user can scan, then STOP and wait for "go":

> **Rough-cut brief — <name>**
> | | |
> |---|---|
> | Source | <mins> min · <lang?> · <WxH> |
> | Manual trims | start: <clip-start or none> · end: <clip-end or none> · remove: <exclude or none> |
> | Remove | silence >0.2s (leave 0.2s buffer) · filler · stutters |
> | Keep | pauses after questions / sentence ends (up to 0.8s) |
> | Semantic | <on: repeated takes/false starts — talking-head | off for meetings/--safe> |
> | Model | <model> on <device> · est ~<n> min |
> | Intro / Outro | intro.mp4 (front) · outro.mp4 (end)  <or "skipped"> |
> | Output | new CapCut draft `<job>_roughcut` (CapCut must be CLOSED) |
>
> Reply **"go"** to proceed, or tell me adjustments.

Only continue once the user approves. If they request changes, adjust flags
(`--min-cut`, `--sentence-pause`, `--model`, `--no-branding`) and re-show the brief.

## 3. Transcribe (after approval)
```
./.venv/Scripts/python.exe -m roughcut.pipeline "<video>" --name <job> \
    --model <model> --device cuda --compute float16 --no-render \
    [--clip-start mm:ss] [--clip-end mm:ss] [--exclude "a-b,c-d"]
```
This writes transcript.json + a baseline edl.json + cuts_report.md. (Pass any
manual trims from step 1.5 here so the review reflects them.)
Long files exceed the 10-min foreground limit — run with `run_in_background: true`.

## 5. Semantic pass (skip if --safe or it's a live meeting)
Read `jobs/<job>/transcript.json`. Flag false starts and repeated takes (keep the
best take). For `--longform`, work in ~10-15 min windows. Write
`jobs/<job>/semantic_cuts.json` → `{"cut_word_indices":[...], "notes":[...]}`.
Be conservative (un-cutting in CapCut is harder than cutting more). Then re-run
decide by repeating step 3 without `--model` download cost (transcript is cached).

## 6. Review
Show the summary from `jobs/<job>/cuts_report.md` (orig→cut, % removed, segments)
and ask the user to confirm or adjust before building.

## 7. Build the CapCut draft (after approval)
Confirm CapCut is closed:
```
powershell -c "[bool](Get-Process CapCut -ErrorAction SilentlyContinue)"
```
If `True`, ask the user to close it. Then build (intro/outro auto-applied from
`assets/`):
```
./.venv/Scripts/python.exe -m roughcut.pipeline "<video>" --name <job> \
    --no-render --build --draft-name "<job>_roughcut" \
    [--clip-start mm:ss] [--clip-end mm:ss] [--exclude "a-b,c-d"]
```
(pass the SAME trim flags used in step 3; add `--no-branding` to skip intro/outro).
Drafts **auto-version**: the first build is `<job>_roughcut`, re-edits become
`_v2`, `_v3`, ... so a draft already polished in CapCut is never overwritten (use
`--overwrite` only if the user explicitly wants to replace it). The build prints
the actual draft name — report that. Tell the user to open CapCut → the project
shows intro → cut content → outro, every cut editable.

## Re-editing a past project
If `jobs/<job>/transcript.json` already exists, skip transcription — just re-run
the decide+build with new settings (cached transcript reused automatically). Use
`--fresh` only to re-transcribe (e.g. switch to `large-v3`).

## Notes
- Only ever CREATES drafts; never edits existing ones.
- If segments exceed ~1500, suggest splitting into per-section drafts.
- Cut quality depends on transcript quality — use `large-v3` for important or
  Taglish footage.
