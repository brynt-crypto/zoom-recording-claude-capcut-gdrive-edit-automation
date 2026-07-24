"""Resolved paths and constants for the Drive layer.

Every private, machine-specific value here is read from the environment (or a
repo-root ``.env`` file) so this repo can be shared publicly. Copy
``.env.example`` to ``.env`` and fill in your own Google Drive account + folders
— see the "Setup" section of the README.

If a value is left unset, the Drive stages (scan / ingest / upload) simply find
no folder and no-op. Every non-Drive stage (transcribe / roughcut / finishing)
still works without any of these set — only ``/scan`` needs them live.
"""
from __future__ import annotations
import os
import sys

# Repo root (this file lives in <root>/drive_sync/).
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_dotenv() -> dict:
    """Best-effort parse of a repo-root ``.env`` (KEY=VALUE per line). No
    dependency on python-dotenv. Returns {} if the file is absent."""
    env: dict = {}
    path = os.path.join(BASE, ".env")
    if not os.path.exists(path):
        return env
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


_DOTENV = _read_dotenv()


def _env(name: str, default: str = "") -> str:
    """Environment variable, falling back to the repo-root ``.env``, then
    ``default``."""
    val = os.environ.get(name)
    if val:
        return val
    return _DOTENV.get(name, default)


# --- Drive folders -----------------------------------------------------------
# Point these at your own Google Drive for Desktop folders. On Windows, Drive
# mounts at G:\ ; on macOS under ~/Library/CloudStorage/GoogleDrive-<email>/.
# Set full paths in .env (see .env.example):
#
#   DRIVE_INPUT_DIR         - where new Zoom recordings land (scanned for footage)
#   DRIVE_EXPORT_DIR        - where you export the finished edit from CapCut
#   DRIVE_UPLOAD_DIR        - Team Drive destination for approved finished edits
#   DRIVE_UPLOAD_FOLDER_URL - web URL of that upload folder (shown to the user)
#
# macOS convenience: if you set GDRIVE_EMAIL plus the *_NAME folder vars instead
# of full DRIVE_* paths, the CloudStorage mount root is derived for you.
INPUT_DIRS = [d for d in [_env("DRIVE_INPUT_DIR")] if d]
EXPORT_DIR = _env("DRIVE_EXPORT_DIR")
UPLOAD_DIR = _env("DRIVE_UPLOAD_DIR")
UPLOAD_LINK = _env("DRIVE_UPLOAD_FOLDER_URL")

# --- macOS convenience derivation --------------------------------------------
# Google Drive for Desktop on macOS mounts under ~/Library/CloudStorage/ as a
# folder named "GoogleDrive-<account-email>". If you didn't set the full DRIVE_*
# paths above, we build them from GDRIVE_EMAIL + the folder-name vars so a Mac
# setup only needs the account email and a couple of folder names in .env.
if sys.platform == "darwin":
    _email = _env("GDRIVE_EMAIL")
    if _email:
        _gdrive = os.path.expanduser(
            f"~/Library/CloudStorage/GoogleDrive-{_email}"
        )
        _input_name = _env("DRIVE_INPUT_FOLDER_NAME")
        _upload_name = _env("DRIVE_UPLOAD_FOLDER_NAME")
        if not INPUT_DIRS and _input_name:
            INPUT_DIRS = [os.path.join(_gdrive, "My Drive", _input_name)]
        if not UPLOAD_DIR and _upload_name:
            UPLOAD_DIR = os.path.join(_gdrive, "My Drive", _upload_name)

# --- Local working folders (reuse the rough-cut drop folder) -----------------
INBOX_DIR = os.path.join(BASE, "assets", "to_edit")

# --- State ledger ------------------------------------------------------------
STATE_FILE = os.path.join(BASE, "drive_sync", "state.json")

# --- File types --------------------------------------------------------------
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"}
