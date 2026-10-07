# Setup — macOS

## 1. Prerequisites

- **CapCut desktop** (International v8.x).
- **ffmpeg / ffprobe** on your `PATH` (`brew install ffmpeg`).
- **Python 3.11+**.

## 2. The virtualenv must live on local disk

> ⚠️ **Never create the venv inside the project folder when the project sits in
> OneDrive or iCloud.** Those are File Provider mounts: they dehydrate files
> into cloud placeholders whose reads **hang forever instead of failing**, so
> imports freeze with no error and no traceback. (Hit on 2026-08-20.)

```bash
python3 -m venv ~/.venvs/capcut-mac
~/.venvs/capcut-mac/bin/python -m pip install -r requirements.txt
~/.venvs/capcut-mac/bin/python -m playwright install chromium   # ~93 MB, once
```

Copy static `ffmpeg` / `ffprobe` binaries into `~/.venvs/capcut-mac/bin/`, or
make sure Homebrew's are on `PATH` when you run the pipeline:

```bash
export PATH="$HOME/.venvs/capcut-mac/bin:$PATH"
```

Everything below assumes that `PATH` and `python` = `~/.venvs/capcut-mac/bin/python`.

## 3. Configure

```bash
cp .env.example .env
```

Fill in what you need — every variable is optional:

| Variable | What it does |
|---|---|
| `MEDIA_ROOT`, `JOBS_DIR`, `OUTPUT_DIR`, `WORK_DIR` | move the big files out of the project (see below) |
| `HOST_NAMES` | the only name allowed on screen in a lower third |
| `DRIVE_*`, `GDRIVE_EMAIL` | the Google Drive pipeline (`/scan`); skip it and everything else still works |
| `ROUGHCUT_SCAN_DIRS` | extra folders to scan for source video |
| `GEMINI_API_KEY` | only for `/animate` with Google Imagen |

Google Drive for Desktop mounts at `~/Library/CloudStorage/GoogleDrive-<email>/`,
which the code auto-detects from `GDRIVE_EMAIL`.

## 4. Keep the media off the synced folder

Source video, job files and exports are large, and they hit the same OneDrive
placeholder problem — plus **CapCut is sandboxed on macOS and cannot read media
inside OneDrive at all**. Point them at local disk:

```
MEDIA_ROOT=/Users/you/Movies/CapCutPipeline/media
JOBS_DIR=/Users/you/Movies/CapCutPipeline/jobs
OUTPUT_DIR=/Users/you/Movies/CapCutPipeline/outputs
WORK_DIR=/Users/you/Movies/CapCutPipeline/work
```

Put `Intro.mp4` and `Outro.mp4` at the top of `MEDIA_ROOT`, source video in
`MEDIA_ROOT/to_edit/`, and style references in `MEDIA_ROOT/style_ref/`.

## 5. Check it works

```bash
python -m pytest -q                       # the suite needs ffmpeg
python -m roughcut.discover --limit 5     # lists footage it can see
```

## Notes specific to this machine

- There is **no NVIDIA GPU**: transcription runs on CPU. Pass
  `--device cpu --compute int8`; the code also downgrades `cuda` → `cpu` on
  non-Windows automatically, so it will not crash either way. Expect roughly
  3× real time with the `base` model.
- "Is CapCut running?" is `pgrep -x CapCut` (it must print nothing before a build).
