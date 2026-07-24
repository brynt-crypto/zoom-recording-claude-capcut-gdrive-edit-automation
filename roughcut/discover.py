"""Find candidate source videos for /roughcut.

Strategy: list the drop-folder (assets/to_edit/) first; if it's empty, scan the
user's main video locations and return the most recently modified clips. Prints
a numbered, human-scannable table for the user to pick from.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

from . import config
from .util import probe, hms

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"}
# Don't surface the tool's own working output as "footage to edit".
_PROJECT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {str(_PROJECT / "jobs"), str(_PROJECT / "work"),
                str(_PROJECT / "sandbox_drafts"), str(_PROJECT / ".venv")}


def _excluded(p: Path) -> bool:
    s = str(p)
    return any(s.startswith(x) for x in EXCLUDE_DIRS)


def _scan(dirs, recursive=True, limit=400):
    found = []
    for d in dirs:
        base = Path(d)
        if not base.exists():
            continue
        it = base.rglob("*") if recursive else base.glob("*")
        for p in it:
            if p.suffix.lower() in VIDEO_EXTS and p.is_file() and not _excluded(p):
                try:
                    found.append((p, p.stat().st_mtime, p.stat().st_size))
                except OSError:
                    pass
            if len(found) >= limit:
                break
    return found


def discover(limit: int = 25, with_duration: bool = True) -> list[dict]:
    inbox = Path(config.INBOX_DIR)
    items = _scan([config.INBOX_DIR], recursive=True) if inbox.exists() else []
    source = "drop-folder (assets/to_edit)"
    if not items:
        items = _scan(config.SCAN_DIRS, recursive=True)
        source = "scan (video folders)"

    items.sort(key=lambda t: t[1], reverse=True)  # newest first
    items = items[:limit]

    out = []
    for p, mtime, size in items:
        rec = {"path": str(p), "name": p.name,
               "size_mb": round(size / 1048576, 1), "mtime": mtime}
        if with_duration:
            try:
                rec["minutes"] = round(probe(str(p))["duration"] / 60, 1)
            except Exception:
                rec["minutes"] = None
        out.append(rec)
    return {"source": source, "items": out}


def main() -> None:
    ap = argparse.ArgumentParser(description="List candidate videos to edit")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-duration", action="store_true")
    a = ap.parse_args()
    res = discover(limit=a.limit, with_duration=not a.no_duration)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    print(f"source: {res['source']}\n")
    for i, r in enumerate(res["items"], 1):
        mins = f"{r['minutes']:>5} min" if r.get("minutes") is not None else "   ? min"
        print(f"  [{i:2}] {mins}  {r['size_mb']:>7} MB  {r['name']}")
        print(f"        {r['path']}")


if __name__ == "__main__":
    main()
