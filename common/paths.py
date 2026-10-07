"""Where the big things live.

Source video, per-job working files and exports are large and disposable; the
repo is neither. Every one of these locations can be moved out of the project
folder by setting the matching variable in ``.env`` — which is also how you get
them off a synced drive (OneDrive dehydrates files into cloud placeholders whose
reads hang forever instead of failing).

  MEDIA_ROOT   branding clips, the to_edit drop-folder, style references
  JOBS_DIR     per-job working files (transcripts, EDLs, manifests, card PNGs)
  OUTPUT_DIR   finished exports
  WORK_DIR     scratch renders

Defaults keep everything inside the project, so an unconfigured checkout behaves
exactly as before.
"""
from __future__ import annotations
from pathlib import Path

from .env import BASE, env_path

MEDIA_ROOT = env_path("MEDIA_ROOT", BASE / "assets")
JOBS_DIR = env_path("JOBS_DIR", BASE / "jobs")
OUTPUT_DIR = env_path("OUTPUT_DIR", BASE / "outputs")
WORK_DIR = env_path("WORK_DIR", BASE / "work")

INBOX_DIR = MEDIA_ROOT / "to_edit"
STYLE_REF_DIR = MEDIA_ROOT / "style_ref"


def job_dir(job: str, *, create: bool = True) -> Path:
    """Working directory for one job."""
    d = JOBS_DIR / job
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def media_path(rel: str) -> Path:
    """Path inside MEDIA_ROOT, e.g. ``media_path("to_edit/2026-09-11.mp4")``."""
    return MEDIA_ROOT / rel
