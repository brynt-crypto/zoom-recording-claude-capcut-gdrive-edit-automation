# Setup — Windows

## 1. Prerequisites

- **CapCut desktop** (International v8.x).
- **ffmpeg / ffprobe** on your `PATH`.
- **Python 3.11+**.
- An NVIDIA GPU is optional but makes transcription far faster (`--device cuda`).

## 2. Virtualenv

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium   # ~93 MB, once
```

Everything below assumes `python` = `.venv\Scripts\python.exe` (activate the
venv, or spell out that path).

The GPU wheels in `requirements.txt` (`nvidia-*`, `comtypes`, `uiautomation`)
are marked `sys_platform == "win32"`, so they install here and are skipped on
macOS.

## 3. Configure

```powershell
copy .env.example .env
```

Fill in what you need — every variable is optional:

| Variable | What it does |
|---|---|
| `MEDIA_ROOT`, `JOBS_DIR`, `OUTPUT_DIR`, `WORK_DIR` | move the big files off the synced project folder |
| `HOST_NAMES` | the only name allowed on screen in a lower third |
| `DRIVE_*` | the Google Drive pipeline (`/scan`); Drive for Desktop usually mounts at `G:\` |
| `ROUGHCUT_SCAN_DIRS` | extra folders to scan for source video (`;`-separated here) |
| `GEMINI_API_KEY` | only for `/animate` with Google Imagen |

Example:

```
MEDIA_ROOT=D:\CapCutPipeline\media
JOBS_DIR=D:\CapCutPipeline\jobs
OUTPUT_DIR=D:\CapCutPipeline\outputs
DRIVE_INPUT_DIR=G:\My Drive\Zoom Recordings
```

## 4. Check it works

```powershell
python -m pytest -q                      # the suite needs ffmpeg
python -m roughcut.discover --limit 5    # lists footage it can see
```

## Notes

- "Is CapCut running?" is
  `powershell -c "[bool](Get-Process CapCut -ErrorAction SilentlyContinue)"` —
  it must be `False` before a build.
- With an NVIDIA GPU, pass `--device cuda` for a large speedup on long-form
  recordings.
