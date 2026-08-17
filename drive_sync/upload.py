"""Upload a finished export to the team Drive folder (a local copy that syncs).

Usage:
  python -m drive_sync.upload "Ai Mastery Zoom Jun25 (CFE Edit).mp4"
  python -m drive_sync.upload --path "C:\\full\\path.mp4" --job ai_mastery_2026-06-25
  python -m drive_sync.upload "name.mp4" --overwrite     # replace if it exists

Refuses to clobber an existing same-name file unless --overwrite is given.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path

from . import config, state


def _find_export(name_or_path: str) -> Path | None:
    p = Path(name_or_path)
    if p.is_file():
        return p
    cand = Path(config.EXPORT_DIR) / name_or_path
    return cand if cand.is_file() else None


def _source_for_job(job: str | None) -> str | None:
    if not job:
        return None
    for src_name, entry in state.load().get("processed", {}).items():
        if entry.get("job") == job:
            return src_name
    return None


def upload(name_or_path: str, job: str | None = None, overwrite: bool = False) -> dict:
    src = _find_export(name_or_path)
    if src is None:
        raise FileNotFoundError(f"export not found in {config.EXPORT_DIR!r}: {name_or_path!r}")

    dest_dir = Path(config.UPLOAD_DIR)
    if not dest_dir.is_dir():
        raise FileNotFoundError(
            f"team Drive folder not found (is Google Drive running?): {dest_dir}")
    dest = dest_dir / src.name

    if dest.exists() and not overwrite:
        if dest.stat().st_size == src.stat().st_size:
            print(f"Already uploaded (same size): {dest}")
            _record(job, src.name)
            return {"export": src.name, "dest": str(dest),
                    "status": "already_uploaded", "link": config.UPLOAD_LINK}
        raise FileExistsError(
            f"a different file with this name already exists at the destination; "
            f"re-run with --overwrite to replace: {dest}")

    print(f"Uploading {src.name}\n   -> {dest}  ({src.stat().st_size/1024/1024:.1f} MB) ...")
    shutil.copy2(src, dest)
    if dest.stat().st_size != src.stat().st_size:
        raise IOError("upload size mismatch after copy")
    print("Upload complete (Google Drive will finish syncing it shortly).")

    _record(job, src.name)
    return {"export": src.name, "dest": str(dest),
            "status": "uploaded", "link": config.UPLOAD_LINK}


def _record(job: str | None, export_name: str) -> None:
    src_name = _source_for_job(job)
    if src_name:
        state.mark(src_name, exported=export_name, uploaded_at=state.now())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Upload an export to the team Drive folder.")
    ap.add_argument("name", nargs="?", help="export filename within the export folder")
    ap.add_argument("--path", help="absolute path to the export")
    ap.add_argument("--job", help="job slug, to update the ledger")
    ap.add_argument("--overwrite", action="store_true", help="replace an existing file")
    args = ap.parse_args(argv)

    target = args.path or args.name
    if not target:
        ap.error("provide a filename or --path")

    result = upload(target, job=args.job, overwrite=args.overwrite)
    print("\nDRIVE_SYNC_JSON")
    print(json.dumps(result, ensure_ascii=False))
    print("END_DRIVE_SYNC_JSON")
    return 0


if __name__ == "__main__":
    sys.exit(main())
