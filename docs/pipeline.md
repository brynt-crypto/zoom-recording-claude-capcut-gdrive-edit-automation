# The pipeline, stage by stage

```
Drive recording ─▶ censor ─▶ rough cut ─▶ finishing (CFE Standard) ─▶ export ─▶ upload
                   blur      cuts +        subtitles, cards,           CapCut     Drive
                   & mute    branding      motion graphics, bleeps     (you)
```

Every stage stops for approval. Nothing overwrites a draft you have polished.

## 0. Ingest — `/scan`

Watches the Google Drive folder for new Zoom recordings, copies one into the
drop-folder and picks a job slug for it. The ledger of what has been processed
lives in `drive_sync/state.json` (per machine, gitignored).

Skip this entirely if you are not using Drive: drop a file in
`MEDIA_ROOT/to_edit/` and start at the rough cut.

## 1. Censor — `/censor`

Blurs screen regions and silences spans **in the source**, before any edit, so
no later stage ever sees an API key or a client's name. Plan → review gate →
encode → verify. See [censoring.md](censoring.md).

Produces `<job>_censored.mp4`, which becomes the source for everything after it.

## 2. Rough cut — `/roughcut`

1. Pick the file (drop-folder first, then your video folders).
2. Brief — a table of exactly what will happen. Nothing runs until you say go.
3. Transcribe: 16 kHz audio → word-level transcript (faster-whisper).
4. Decide: remove dead air beyond `MIN_CUT`, filler words and stutters; keep
   comprehension pauses after questions and sentence ends.
5. Semantic pass (Claude): drop false starts and repeated takes, keep the best
   one. Skipped for live meetings and with `--safe`.
6. Review gate.
7. Build the CapCut draft, with `Intro.mp4` prepended and `Outro.mp4` appended
   as separate, editable segments.

Artifacts land in `JOBS_DIR/<job>/`: `transcript.json`, `edl.json`,
`cuts_report.md`, optional `preview.mp4`.

Tunables live in `roughcut/config.py` (`MIN_CUT`, `KEEP_PAUSE`, `SENTENCE_PAUSE`,
`PAD_BEFORE/AFTER`, `FILLER_WORDS`), or per run: `--min-cut`,
`--sentence-pause`, `--model`, `--no-branding`.

## 3. Finishing — `/capcut-finishing-editor` (CFE Standard)

Polishes the rough cut without re-cutting it: continuous captions, glass cards,
motion-graphic treatments (process flows, checklists, timelines, comparisons,
charts, quotes, stat figures, lower thirds, CTAs), punch-ins, pseudo-split,
staggered multi-layer reveals, and bleep censoring.

```
python -m finishing.pipeline <job> --prep      # enrich transcript + style frames
#   Claude writes JOBS_DIR/<job>/finishing_manifest.json, you review it
python -m finishing.pipeline <job> --captions   # build
```

Writes a new `<Job> (CFE Standard)` draft — the rough-cut draft is never touched,
and a re-run auto-versions to `v2`, `v3`, …

There is one engine. The old v1 overlay engine was retired on 2026-09-17; jobs
finished before then keep their `finishing_manifest_v2.json`, which still builds
via `--manifest`.

## 4. Export

You export from CapCut by hand — that is the point of the whole pipeline: every
cut, card and caption is still a draggable segment you can fix first.

## 5. Upload — `/scan` (continued), `/describe`

Uploads the export to the Drive folder, then `/describe` writes the course-portal
lesson description from the *edited* transcript.

---

## The rules that keep it safe

- **CLOSE CapCut before any build.** CapCut caches drafts in memory and
  overwrites them on exit; a new draft also will not appear until you restart it.
  The pipeline checks and warns.
- **The writer only creates drafts.** It never edits or deletes an existing one.
- **To delete a version, delete its draft folder on disk** — not inside CapCut.
  CapCut shares imported media between drafts, so deleting one version in the
  app can garbage-collect media the others still point at, turning them into a
  black screen with no audio. If that already happened: rebuild, the cached
  transcript and EDL relink the real file in seconds.
- **Keep the raw source in place.** Every draft references it by path.
- **Transcript quality drives cut quality.** `base` is fast but rough on
  non-English/Taglish; use `--model medium` or `large-v3` for anything that
  matters.
