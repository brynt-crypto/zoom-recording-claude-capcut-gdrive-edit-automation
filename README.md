# Rough-Cut Editor — Claude Code → CapCut

Prompt Claude Code to turn raw footage into an **editable CapCut draft** with
silences, filler words, stutters, and repeated takes removed. You then do final
polish in CapCut — every cut is still draggable/restorable.

There is no "upload": CapCut desktop edits local files. The pipeline writes a new
CapCut **draft** that references your raw clip with the cuts already applied.

## How it works

```
pick file → BRIEF (you approve) → transcribe (GPU) → decide cuts → REVIEW → CapCut draft (+intro/outro)
                                                      ↑ Claude semantic pass
```

0. **pick file** — `/roughcut` lists the drop-folder `assets/to_edit/` first, else
   scans your video folders (`~/Videos` + `~/Downloads`, configurable); you pick one.
1. **brief** — a scannable table of exactly what will happen; nothing runs until you say "go".
2. **transcribe** — 16 kHz audio (ffmpeg) → word-level transcript (faster-whisper, GPU).
3. **decide** — remove dead air **>0.2s (leaving a 0.2s buffer)**, filler, stutters;
   **keep** comprehension pauses after questions/sentence ends (up to 0.8s); widened
   padding so words never clip.
4. **semantic** (Claude) — remove false starts / repeated takes, keep the best take
   (talking-head; skipped for live meetings or `--safe`).
5. **review** — you approve the cut summary.
6. **build_draft** — new CapCut draft with **intro.mp4 prepended + outro.mp4 appended**
   as separate editable segments; open CapCut to polish.

## Setup (connect your own accounts)

Nothing private is baked into this repo — you supply your own paths, folders, and
keys via a local `.env` file (gitignored).

1. **Install deps** into a virtualenv:
   ```bash
   python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium                    # for finishing style frames
   ```
   You also need **ffmpeg** on your PATH and **CapCut desktop** installed.
2. **Copy the env template** and fill in your own values:
   ```bash
   cp .env.example .env
   ```
   - `DRIVE_*` — only for the `/scan` Google-Drive pipeline. Point them at your
     own Google Drive for Desktop folders. Leave blank to skip Drive entirely;
     `/roughcut` and finishing work without it.
   - `ROUGHCUT_SCAN_DIRS` — extra folders to scan for source video (optional).
   - `GEMINI_API_KEY` — only for the `/animate` feature (Google Imagen).
3. **Branding** — replace `assets/Intro.mp4` / `assets/Outro.mp4` with your own
   (same filenames) to rebrand every rough cut. Skip per-run with `--no-branding`.

## Usage (via Claude Code)

```
/roughcut                       # lists files to pick from, then shows a brief
/roughcut "Raw 2"               # match by name; still confirms via the brief
/roughcut <path> --longform --model large-v3   # 1h+ recordings, max quality
/roughcut <path> --safe         # mechanical cuts only (no semantic pass)
/roughcut <path> --no-branding  # skip intro/outro
```

The `/roughcut` command picks the file, shows the brief, waits for approval, runs,
shows the review, then builds the draft. See `.claude/commands/roughcut.md`.

## Manual timestamp trims

Every run asks whether you want to remove specific parts before auto-cutting:
- `--clip-start mm:ss` — drop everything before this (intro/setup pre-roll)
- `--clip-end mm:ss` — drop everything after this
- `--exclude "12:30-15:00,40:00-41:10"` — remove specific mid ranges

Timestamps accept `ss`, `mm:ss`, or `hh:mm:ss`. These are applied as hard cuts
alongside the automatic ones.

## Re-editing a past project (no re-transcribe)

Each job caches its transcript in `jobs/<name>/transcript.json` (the slow GPU
step). Re-editing just re-runs the fast decide + build with new settings:

```bash
PY="./.venv/Scripts/python.exe"
# change aggressiveness / trims / branding and rebuild — seconds, no transcription:
$PY -m roughcut.pipeline "VIDEO" --name <job> --no-render --build \
    --draft-name "<job>_v2" --min-cut 0.3 --exclude "5:00-6:00"
```

- Reuses the cached transcript automatically (add `--fresh` only to re-transcribe,
  e.g. to switch to `large-v3`).
- **Use a new `--draft-name` for re-edits** if you've already polished the old
  draft in CapCut — rebuilding the same name overwrites it.
- The original raw video is never modified.

## ⚠️ Deleting versions (avoid the black-screen trap)

CapCut shares imported media **between drafts**. If several versions point at the
same source clip and you **delete one version inside CapCut**, CapCut may garbage-
collect the shared media and **break the other versions** — their main video turns
into a `##_material_placeholder_…##` and plays as a **black screen with no audio**
(the intro/outro still show, since they have their own paths).

- **To remove a version:** delete its **draft folder on disk**
  (`…\com.lveditor.draft\<name>\`) instead of deleting it inside CapCut. That
  removes only that draft and never touches shared media.
- **If a version already went black:** just rebuild it — the cached transcript +
  EDL relink the real file in seconds (`build` with `--overwrite`).
- Keep your **raw source videos in place**; every draft references them by path.

## Branding (intro / outro)

Drop `intro.mp4` and `outro.mp4` in **`assets/`** (exact names). They're added to
every rough cut as separate, editable segments (front and end). Replace the files
to rebrand — no code change. Skip per-run with `--no-branding`.

## Manual / CLI

```bash
PY="./.venv/Scripts/python.exe"
$PY -m roughcut.pipeline "VIDEO" --name myjob --model base --no-render   # transcribe+decide
# (optionally write jobs/myjob/semantic_cuts.json with {"cut_word_indices":[...]})
$PY -m roughcut.pipeline "VIDEO" --name myjob                            # decide + preview
$PY -m roughcut.pipeline "VIDEO" --name myjob --no-render --build \
    --draft-name "myjob_roughcut"                                        # CapCut draft
```

Artifacts land in `jobs/<name>/`: `transcript.json`, `edl.json`, `cuts_report.md`,
`preview.mp4`, optional `semantic_cuts.json`.

## ⚠️ Rules

- **CLOSE CapCut before building a draft.** CapCut caches drafts in memory and
  overwrites them on exit; a new draft also won't appear until you restart it.
  The pipeline checks and warns.
- The writer **only creates new drafts** — it never touches your existing 259 drafts.
- **Transcript quality drives cut quality.** `base` is fast but rough on
  non-English/Taglish; use `--model medium` or `large-v3` for important footage.
- **CapCut International v8.x** drafts are plain JSON (verified). If a future
  CapCut update encrypts drafts (as JianYing 6.0+ did), the `preview.mp4` path
  still works, and we fall back to template-cloning one of your real drafts.

## Performance (this machine)

- faster-whisper `base` on CPU ≈ **3.4× real-time** → ~18 min for 1 h, ~70 min for 4 h.
- Use `--device cuda` with an NVIDIA GPU for a large speedup on long-form.

## Tuning

Edit `roughcut/config.py`:
- `MIN_CUT` (0.20) — only remove dead air beyond this.
- `KEEP_PAUSE` (0.20) — silence left in a trimmed gap.
- `SENTENCE_PAUSE` (0.80) — comprehension pause kept after `?`/`.`/`!`.
- `PAD_BEFORE` / `PAD_AFTER` (0.12 / 0.20) — buffer around words (anti-clip).
- `FILLER_WORDS` — English + Taglish/Tagalog filler list.
- `INTRO_PATH` / `OUTRO_PATH` / `INBOX_DIR` / `SCAN_DIRS` — branding + file-pick locations.

Or per-run: `--min-cut`, `--sentence-pause`, `--model`, `--no-branding`.

## Layout

```
roughcut/
  config.py       tunables (thresholds, filler words)
  transcribe.py   video -> transcript.json
  silence.py      ffmpeg silencedetect (secondary signal)
  decide.py       transcript -> edl.json + cuts_report.md
  render.py       edl -> preview.mp4
  build_draft.py  edl -> CapCut draft (pycapcut)
  pipeline.py     orchestrates everything
.claude/commands/roughcut.md   the /roughcut command
jobs/<name>/      per-video artifacts
```

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
