"""Post-approval cleanup: reclaim disk once an approved edit is safely in Drive.

SAFETY MODEL — nothing is deleted unless the uploaded copy is verified first:
  1. the file must exist in the team Drive folder (config.UPLOAD_DIR), and
  2. its size must match the local export byte-for-byte.
If that check fails, this module deletes NOTHING and says why.

Never touched:
  - the original recording in the Drive input folder (the master),
  - the APPROVED CapCut draft (so the edit stays re-editable),
  - jobs/<job>/ working files (so finishing can re-run without re-transcribing),
    except jobs/<job>/audio.wav, which is listed and only removed with
    --include-audio.

Every run prints the full reclaimable list with sizes and what breaks if each
item goes, even when the upload is not confirmed yet and nothing can be deleted.
Dry-run by default; pass --confirm to actually delete.

Usage:
  python -m drive_sync.cleanup <job> --export "name.mp4"
  python -m drive_sync.cleanup <job> --export "name.mp4" --confirm
  python -m drive_sync.cleanup <job> --export "name.mp4" --confirm --include-roughcut
  python -m drive_sync.cleanup <job> --export "name.mp4" --confirm --include-audio
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from . import config, state


# --- helpers -----------------------------------------------------------------

def _size(p: Path) -> int:
    """Bytes for a file, or the recursive total for a directory."""
    if p.is_file():
        return p.stat().st_size
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def _human(n: int) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if x < 1024 or unit == "GB":
            return f"{x:.1f}{unit}"
        x /= 1024
    return f"{x:.1f}GB"


def _drafts_root() -> Path | None:
    try:
        from roughcut.build_draft import DEFAULT_DRAFTS_ROOT
        return Path(DEFAULT_DRAFTS_ROOT)
    except Exception:
        return None


# --- verification ------------------------------------------------------------

def verify_uploaded(export_name: str) -> dict:
    """Confirm the export is present in the team Drive folder and size-matched.

    Returns {"ok": bool, "reason": str, "dest": str, "dest_size": int,
             "local_size": int|None}.
    """
    dest = Path(config.UPLOAD_DIR) / export_name
    local = Path(config.EXPORT_DIR) / export_name

    if not Path(config.UPLOAD_DIR).is_dir():
        return {"ok": False, "reason": "team Drive folder not found (is Google Drive running?)",
                "dest": str(dest), "dest_size": 0, "local_size": None}
    if not dest.is_file():
        return {"ok": False, "reason": f"not found in the team Drive folder: {export_name}",
                "dest": str(dest), "dest_size": 0, "local_size": None}

    dest_size = dest.stat().st_size
    if dest_size == 0:
        return {"ok": False, "reason": "uploaded file is 0 bytes (still syncing?)",
                "dest": str(dest), "dest_size": 0, "local_size": None}

    local_size = local.stat().st_size if local.is_file() else None
    if local_size is not None and local_size != dest_size:
        return {"ok": False,
                "reason": (f"size mismatch — local {_human(local_size)} vs "
                           f"Drive {_human(dest_size)} (upload may still be in progress)"),
                "dest": str(dest), "dest_size": dest_size, "local_size": local_size}

    return {"ok": True, "reason": "verified in Drive", "dest": str(dest),
            "dest_size": dest_size, "local_size": local_size}


# --- what can be removed -----------------------------------------------------

def _approved_draft(job: str) -> str | None:
    """Name of the highest-versioned finishing draft for this job, if any."""
    root = _drafts_root()
    if not (root and root.is_dir()):
        return None
    pretty = re.escape(job.replace("_", " ").title())
    pat = re.compile(rf"^(?:{re.escape(job)}|{pretty})[ _]\((?:CFE Standard|CFE Edit)\)"
                     rf"(?:[ _]v(\d+))?$")
    found = [(int(m.group(1) or 1), d.name) for d in root.iterdir()
             if d.is_dir() and (m := pat.match(d.name))]
    return max(found)[1] if found else None


def plan(job: str, export_name: str, include_roughcut: bool = False,
         include_audio: bool = False) -> dict:
    """Build the list of removable items. Does not delete anything.

    Each item carries `breaks`: what stops working if it is deleted.
    Opt-in items (`optional: True`) are listed but only deleted with their flag.
    """
    items: list[dict] = []
    approved = _approved_draft(job)

    # 1. Ingested source copy (the master stays in the Drive input folder).
    inbox = Path(config.INBOX_DIR)
    if inbox.is_dir():
        for f in sorted(inbox.iterdir()):
            if f.is_file() and f.stem == job and f.suffix.lower() in config.VIDEO_EXTS:
                items.append({"kind": "source_copy", "path": str(f), "size": _size(f),
                              "note": "ingested copy — original remains in Drive",
                              "breaks": "nothing; re-ingest from Drive if needed"})

    # 2. Local export (already verified present in Drive by the caller).
    local_export = Path(config.EXPORT_DIR) / export_name
    if local_export.is_file():
        items.append({"kind": "local_export", "path": str(local_export),
                      "size": _size(local_export),
                      "note": "exported video — copy is in the team Drive folder",
                      "breaks": "nothing; the Drive copy is the deliverable"})

    # 3. Media staged outside OneDrive so CapCut (sandboxed) could read it.
    #    Safe once the edit is exported and uploaded — it is only a working copy.
    try:
        from roughcut.mac_compat import STAGE_ROOT
        staged = STAGE_ROOT / job
        if staged.is_dir():
            items.append({"kind": "staged_media", "path": str(staged), "size": _size(staged),
                          "note": "CapCut working copies — originals remain in Drive",
                          "breaks": (f"draft '{approved}' opens black (media missing); "
                                     "only matters to re-export it") if approved
                                    else "any CapCut draft for this job opens black (media missing)"})
    except Exception:
        pass

    # 4. Superseded CapCut drafts: every finishing draft below the highest
    #    version. Matches the current "<Job Title> (CFE Standard) vN" naming and
    #    the older "<job>_(CFE Edit)_vN" drafts still on disk. An unversioned
    #    draft is v1.
    root = _drafts_root()
    if root and root.is_dir():
        pretty = re.escape(job.replace("_", " ").title())
        pat = re.compile(
            rf"^(?:{re.escape(job)}|{pretty})[ _]\((?:CFE Standard|CFE Edit)\)"
            rf"(?:[ _]v(\d+))?$")
        versions: list[tuple[int, Path]] = []
        for d in root.iterdir():
            if not d.is_dir():
                continue
            m = pat.match(d.name)
            if m:
                versions.append((int(m.group(1) or 1), d))
        if versions:
            approved = max(versions, key=lambda t: t[0])[0]
            for n, d in sorted(versions):
                if n < approved:
                    items.append({"kind": "superseded_draft", "path": str(d), "size": _size(d),
                                  "note": f"v{n} — superseded by the approved v{approved}",
                                  "breaks": f"that older draft (v{n}) is gone"})

        if include_roughcut:
            rc = root / f"{job}_roughcut"
            if rc.is_dir():
                items.append({"kind": "roughcut_draft", "path": str(rc), "size": _size(rc),
                              "note": "rough-cut draft — superseded by the finished edit",
                              "breaks": "the rough-cut draft is gone"})

    # 5. Extracted job audio — large and regenerable from the source recording.
    from common.paths import JOBS_DIR
    audio = JOBS_DIR / job / "audio.wav"
    if audio.is_file():
        items.append({"kind": "job_audio", "path": str(audio), "size": _size(audio),
                      "note": "audio extracted for transcription",
                      "breaks": "a finishing re-run has to re-extract it from the source",
                      "optional": not include_audio})

    return {"job": job, "export": export_name, "items": items,
            "total_bytes": sum(i["size"] for i in items if not i.get("optional"))}


def _print_items(items: list[dict]) -> None:
    for i in items:
        tag = "  (opt-in)" if i.get("optional") else ""
        print(f"  - [{i['kind']}] {_human(i['size']):>8}  {i['path']}{tag}")
        print(f"      {i['note']}")
        print(f"      if deleted: {i['breaks']}")


# --- execution ---------------------------------------------------------------

def run(job: str, export_name: str, *, confirm: bool = False,
        include_roughcut: bool = False, include_audio: bool = False) -> dict:
    check = verify_uploaded(export_name)
    p = plan(job, export_name, include_roughcut=include_roughcut,
             include_audio=include_audio)
    p["verified"] = check

    if not check["ok"]:
        p["status"] = "blocked"
        print(f"REFUSING TO DELETE — {check['reason']}")
        print("Nothing was removed. Confirm the upload finished, then re-run.")
        if p["items"]:
            print(f"\nReclaimable once the upload is confirmed "
                  f"({_human(p['total_bytes'])}):")
            _print_items(p["items"])
        return p

    print(f"Verified in Drive: {check['dest']}  ({_human(check['dest_size'])})\n")
    if not p["items"]:
        p["status"] = "nothing_to_do"
        print("Nothing to clean up for this job.")
        return p

    print(f"{'WILL DELETE' if confirm else 'WOULD DELETE'} "
          f"({_human(p['total_bytes'])} total):")
    _print_items(p["items"])

    if not confirm:
        p["status"] = "dry_run"
        print("\nDry run — nothing deleted. Re-run with --confirm to remove these.")
        return p

    removed, failed = [], []
    for i in [i for i in p["items"] if not i.get("optional")]:
        target = Path(i["path"])
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            removed.append(i)
        except OSError as e:
            failed.append({**i, "error": str(e)})

    p["removed"], p["failed"] = removed, failed
    p["freed_bytes"] = sum(i["size"] for i in removed)
    p["status"] = "cleaned" if not failed else "partial"

    src_name = _source_for_job(job)
    if src_name:
        state.mark(src_name, cleaned_at=state.now(),
                   freed_bytes=p["freed_bytes"])

    print(f"\nFreed {_human(p['freed_bytes'])} ({len(removed)} item(s) removed).")
    for f in failed:
        print(f"  FAILED: {f['path']} — {f['error']}")
    return p


def _source_for_job(job: str) -> str | None:
    for src_name, entry in state.load().get("processed", {}).items():
        if entry.get("job") == job:
            return src_name
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Reclaim disk after an approved edit is verified in Drive.")
    ap.add_argument("job", help="job slug")
    ap.add_argument("--export", required=True, help="exported filename that was uploaded")
    ap.add_argument("--confirm", action="store_true",
                    help="actually delete (default is a dry run)")
    ap.add_argument("--include-roughcut", action="store_true",
                    help="also remove the <job>_roughcut draft")
    ap.add_argument("--include-audio", action="store_true",
                    help="also remove jobs/<job>/audio.wav (always listed)")
    args = ap.parse_args(argv)

    result = run(args.job, args.export, confirm=args.confirm,
                 include_roughcut=args.include_roughcut,
                 include_audio=args.include_audio)
    print("\nDRIVE_SYNC_JSON")
    print(json.dumps(result, ensure_ascii=False))
    print("END_DRIVE_SYNC_JSON")
    return 0 if result.get("status") != "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
