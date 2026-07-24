---
description: Turn narration audio into a TED-Ed-style animated explainer — AI stills + Ken Burns motion + your voice — as an editable CapCut draft
argument-hint: [audio path or name] [--provider manual|imagen|codex] [--dry-run] [--reference PATH] [--no-branding]
---

You are running the **/animate** pipeline: narration audio → transcript →
storyboard → scene images → an editable CapCut draft (still images animated with
Ken Burns motion, the user's narration as the soundtrack, per-scene captions).

Engine runs in the venv: `./.venv/Scripts/python.exe -m animate.pipeline ...`

## Image providers (how scene images are produced)
- **manual** (default): the pipeline writes a prompt sheet; the USER generates
  images in ChatGPT/Codex (their subscription) and saves them as
  `scene_<id>.png`. **$0 API cost.** Build picks them up automatically.
- **imagen**: automatic via Google Imagen (needs `GEMINI_API_KEY`; ~$0.04/image).
- **codex**: best-effort shell-out to the `codex` CLI (see note in step 4).

`--dry-run` writes placeholder images (no cost, no key) so you can preview timing
and motion before committing to any provider.

## 0. Pick the narration audio
Look in `assets/to_edit/` first, else ask. Resolve to one absolute path. Job name =
filename stem, spaces → underscores (or `--name`).

## 1. Transcribe (reuses whisper)
```
./.venv/Scripts/python.exe -m animate.pipeline "<audio>" --transcribe --name <job> --device cuda
```
Long files: run in the background. Writes `jobs/<job>/transcript.json`. (Drop
`--device cuda` if there's no GPU.)

## 2. Prep + author the storyboard (you, Claude)
Optional: the user can supply a **reference storyboard/brief** to steer the whole
video. Pass it explicitly, or drop it in `jobs/<job>/reference.*` or
`assets/storyboard_ref/`:
```
./.venv/Scripts/python.exe -m animate.pipeline <job> --prep [--reference "<path>"]
```
Prints narration duration + suggested scene count, reports any reference found, and
writes `jobs/<job>/storyboard.skeleton.json`.

If a reference is reported, **read it first** (`.md`/`.txt` directly; `.pdf` via the
Read tool's page range; view any reference images) and follow it as the creative
direction — map its scene ideas/style onto the real narration timing.

Then read `animate/prompts/00_system.md`, `01_scenes.md`, `02_image_prompts.md`,
`03_storyboard.md`, and `jobs/<job>/transcript.json`. **Write
`jobs/<job>/storyboard.json`**: contiguous scenes from 0.0 to ~the narration
duration, one visual metaphor each, motion varied, captions only for key terms.

## 3. ⛔ REVIEW GATE #1 — approve before generating (do not skip)
Show a table: scene count, and per scene its time span · motion · caption · image
prompt. State the chosen provider and, for `imagen`, the **estimated cost**
(scenes × price). STOP and wait for "go". On changes, edit `storyboard.json` and
re-show. Suggest a free `--dry-run` first to preview timing/motion.

## 4. Produce the scene images
```
./.venv/Scripts/python.exe -m animate.pipeline <job> --generate --provider <manual|imagen|codex> [--dry-run]
```
- **manual**: the command prints a prompt sheet path (`jobs/<job>/scenes/prompt_sheet.md`).
  Give the user those prompts; they generate each image in ChatGPT/Codex and save it
  as `scene_<id>.png` in `jobs/<job>/scenes/`. Re-run `--generate` to confirm all exist.
- **imagen**: generates automatically; report the actual cost. Add `--fast`/`--ultra`
  to change quality/price.
- **codex**: shells `codex exec` per scene, then checks the PNG appeared. Codex is a
  coding agent, so this only works if your Codex setup can emit image files; if it
  can't, it errors per scene — fall back to `manual`.

Generation is idempotent: existing `scene_<id>.png` files are skipped. Regenerate
specific scenes with `--generate --regen 3,7` after editing their prompts.

## 5. REVIEW GATE #2 (optional)
Show the generated PNG paths so the user can eyeball them; regenerate weak scenes.

## 6. Build (CapCut must be CLOSED)
```
powershell -c "[bool](Get-Process CapCut -ErrorAction SilentlyContinue)"
```
If `True`, ask the user to close CapCut, then build:
```
./.venv/Scripts/python.exe -m animate.pipeline <job> --build [--no-branding]
```
Creates `<Job> (Animated)` (auto-versions to ` v2`… on re-runs) in the CapCut
drafts folder. Tell the user to open CapCut → animated scenes + captions +
intro/outro, all editable, with their narration as the audio.

## Notes
- The build only CREATES drafts; it never edits existing ones. If images are
  missing it tells you which scene ids and stops.
- `--dry-run` needs no API key and spends nothing — verify the whole pipeline first.
- Imagen key (only for `--provider imagen`): `setx GEMINI_API_KEY "your-key"` then
  reopen the terminal, or add `GEMINI_API_KEY=your-key` to a repo-root `.env`.
- Re-editing: change `storyboard.json`, then `--generate --regen <ids>` and `--build`.
