"""Scan Drive folders for new footage (default) or detect a manual export.

Usage:
  python -m drive_sync.scan                 # list input recordings, flag NEW
  python -m drive_sync.scan --export        # list export folder, newest first
  python -m drive_sync.scan --export --since <ISO|epoch>   # only files newer

Prints a human-readable table AND a machine-readable JSON block (between the
DRIVE_SYNC_JSON markers) so the /scan command can parse the result reliably.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import config, state
from .names import job_slug


def _list_videos(dirs: list[str]) -> list[dict]:
    out = []
    for d in dirs:
        p = Path(d)
        if not p.is_dir():
            continue
        for f in p.iterdir():
            if f.is_file() and f.suffix.lower() in config.VIDEO_EXTS:
                st = f.stat()
                out.append({
                    "name": f.name,
                    "path": str(f),
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                })
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


def _fmt_size_clean(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}"
        f /= 1024
    return f"{f:.1f}TB"


def _parse_since(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def scan_input() -> dict:
    led = state.load().get("processed", {})
    files = _list_videos(config.INPUT_DIRS)
    new, seen = [], []
    for f in files:
        f["job"] = job_slug(f["name"])
        (seen if f["name"] in led else new).append(f)

    print(f"Scanned {len(config.INPUT_DIRS)} input folder(s): "
          f"{len(new)} new, {len(seen)} already processed.\n")
    if new:
        print("NEW recordings:")
        for f in new:
            print(f"  * {f['name']}  ({_fmt_size_clean(f['size'])})  -> job: {f['job']}")
    else:
        print("No new recordings.")
    if seen:
        print("\nAlready processed:")
        for f in seen:
            print(f"  - {f['name']}")
    return {"mode": "input", "new": new, "seen": seen}


def scan_export(since: float | None) -> dict:
    files = _list_videos([config.EXPORT_DIR])
    if since is not None:
        files = [f for f in files if f["mtime"] > since]
    print(f"Export folder: {len(files)} file(s)"
          + (f" newer than marker" if since is not None else "") + ".\n")
    for f in files:
        ts = datetime.fromtimestamp(f["mtime"]).isoformat(timespec="seconds")
        print(f"  {ts}  {f['name']}  ({_fmt_size_clean(f['size'])})")
    return {"mode": "export", "files": files}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan Drive for new footage / exports.")
    ap.add_argument("--export", action="store_true", help="scan the export folder instead")
    ap.add_argument("--since", help="ISO timestamp or epoch seconds; export mode only")
    args = ap.parse_args(argv)

    result = scan_export(_parse_since(args.since)) if args.export else scan_input()

    print("\nDRIVE_SYNC_JSON")
    print(json.dumps(result, ensure_ascii=False))
    print("END_DRIVE_SYNC_JSON")
    return 0


if __name__ == "__main__":
    sys.exit(main())
