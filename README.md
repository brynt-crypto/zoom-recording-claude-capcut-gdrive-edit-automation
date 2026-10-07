# Auto VEdit — Zoom recording → polished CapCut draft

Turn a raw recording into an **editable CapCut draft**: dead air, filler words
and repeated takes removed, private things blurred and muted, brand intro/outro
in place, captions and motion-graphic cards laid on top — every one of them
still a draggable segment you can fix by hand.

There is no "upload" step and no rendering farm. CapCut desktop edits local
files, so the pipeline writes a **draft** that points at your footage with the
cuts already applied. You do the final polish and export yourself.

```
Drive recording ─▶ censor ─▶ rough cut ─▶ finishing ─▶ export ─▶ upload
```

## Setup

- **macOS** → [docs/setup-mac.md](docs/setup-mac.md)
- **Windows** → [docs/setup-windows.md](docs/setup-windows.md)

Nothing private is baked into this repo: paths, folders, the host's on-screen
name and API keys all come from a local `.env` (gitignored). Start from
`.env.example`.

## Commands

Run through Claude Code; each one stops for your approval at every gate.

| Command | What it does |
|---|---|
| `/scan` | watch Google Drive for new Zoom recordings and run the whole chain |
| `/censor` | blur and mute what must not ship, then verify it frame by frame |
| `/roughcut` | cut silence, filler and repeated takes; add intro + outro |
| `/capcut-finishing-editor` | polish into the **CFE Standard** draft: captions, glass cards, motion graphics, punch-ins, bleeps |
| `/describe` | write the course-portal lesson description from the edited transcript |
| `/animate` | narration audio → a TED-Ed-style animated explainer draft |

Under the hood they are plain Python modules you can run yourself:

```bash
python -m roughcut.pipeline "VIDEO" --name myjob                # transcribe + decide
python -m finishing.pipeline myjob --prep                       # enrich + style frames
python -m finishing.pipeline myjob --captions    # build the draft
python -m censor verify myjob --sheet                           # check a censored master
```

## How it fits together

| Package | Role |
|---|---|
| `roughcut/` | transcribe → decide cuts → EDL → CapCut draft |
| `finishing/` | beats, captions, cards, animations, punch-ins, bleeps |
| `censor/` | blur/mute plan → filter → encode → verify |
| `animate/` | storyboard → scene images → Ken Burns draft |
| `drive_sync/` | Drive ingest, upload, cleanup, lesson descriptions |
| `common/` | `.env` reading and where the big files live |
| `scripts/` | one-off utilities (e.g. a contact sheet of a draft's cards) |

Stage-by-stage detail, tuning knobs and the rules that keep drafts safe:
[docs/pipeline.md](docs/pipeline.md). Censoring: [docs/censoring.md](docs/censoring.md).

## The things that will bite you

- **CLOSE CapCut before a build.** It caches drafts in memory and overwrites
  them on exit.
- **Delete a version by deleting its draft folder on disk,** never inside
  CapCut — CapCut shares media between drafts and can black-screen the others.
- **Keep the big media off OneDrive/iCloud.** Those mounts hand out cloud
  placeholders whose reads hang forever instead of failing, and CapCut for macOS
  is sandboxed out of them entirely. Point `MEDIA_ROOT`, `JOBS_DIR`,
  `OUTPUT_DIR` and `WORK_DIR` at local disk.
- **Transcript quality drives cut quality.** Use `--model medium` or `large-v3`
  for anything that matters.

## Development

```bash
make setup     # venv + deps + playwright chromium
make test      # pytest (needs ffmpeg on PATH)
```

Changes worth knowing about are in [CHANGELOG.md](CHANGELOG.md).

MIT licensed — see [LICENSE](LICENSE).
