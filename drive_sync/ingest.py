"""Copy a chosen Drive recording into the local drop folder for rough-cutting.

Copying locally first means Whisper reads a real local file, not a streamed
Drive-for-Desktop placeholder. Prints a JSON block with {local_path, job}.

Usage:
  python -m drive_sync.ingest "Ai Mastery Zoom Room2026-06-25T16 39 46Z.mp4"
  python -m drive_sync.ingest --path "G:\\full\\path\\to\\file.mp4"
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path

from . import config, state
from .names import job_slug


def _find_source(name_or_path: str) -> Path | None:
    p = Path(name_or_path)
    if p.is_file():
        return p
    for d in config.INPUT_DIRS:
        cand = Path(d) / name_or_path
        if cand.is_file():
            return cand
    return None


def ingest(name_or_path: str) -> dict:
    src = _find_source(name_or_path)
    if src is None:
        raise FileNotFoundError(f"recording not found in input folders: {name_or_path!r}")

    job = job_slug(src.name)
    dest = Path(config.INBOX_DIR) / f"{job}{src.suffix.lower()}"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and dest.stat().st_size == src.stat().st_size:
        print(f"Already ingested (same size): {dest}")
    else:
        print(f"Copying {src.name}\n   -> {dest}  ({src.stat().st_size/1024/1024:.1f} MB) ...")
        shutil.copy2(src, dest)
        if dest.stat().st_size != src.stat().st_size:
            raise IOError("copy size mismatch — Drive file may still be downloading")
        print("Copy complete.")

    state.mark(src.name, job=job, local_path=str(dest),
               ingested_at=state.now(), roughcut="pending", finishing="pending")
    return {"source": src.name, "local_path": str(dest), "job": job}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest a Drive recording locally.")
    ap.add_argument("name", nargs="?", help="filename within an input folder")
    ap.add_argument("--path", help="absolute path to the recording")
    args = ap.parse_args(argv)

    target = args.path or args.name
    if not target:
        ap.error("provide a filename or --path")

    result = ingest(target)
    print("\nDRIVE_SYNC_JSON")
    print(json.dumps(result, ensure_ascii=False))
    print("END_DRIVE_SYNC_JSON")
    return 0


if __name__ == "__main__":
    sys.exit(main())
