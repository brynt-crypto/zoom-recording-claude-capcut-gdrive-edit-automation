"""Course-portal description helper for the /describe command.

Three thin subcommands — Claude does the actual summarizing, this only moves
bytes and reads the transcript:

  text <job>              print the edited video's readable transcript (prose)
  name <job>              print the .txt filename to use + the EXPORT_DIR path
  upload <job> "<txt>"    copy EXPORT_DIR/<txt> -> UPLOAD_DIR/<txt> (Drive syncs)

The description text itself is authored by Claude and written with the native
editor into EXPORT_DIR; this module never generates copy.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path

from . import config, state


# --- transcript text ---------------------------------------------------------
def _job_dir(job: str) -> Path:
    return Path(config.BASE) / "jobs" / job


def transcript_text(job: str) -> dict:
    """Return {text, language, words, source} for the EDITED video.

    Prefers transcript_final.json (post-cut words = what survived the edit);
    falls back to transcript.json segment text if the final transcript is gone.
    """
    jd = _job_dir(job)
    final = jd / "transcript_final.json"
    base = jd / "transcript.json"
    language = None
    if base.exists():
        try:
            language = json.loads(base.read_text(encoding="utf-8-sig")).get("language")
        except (json.JSONDecodeError, OSError):
            pass

    if final.exists():
        d = json.loads(final.read_text(encoding="utf-8-sig"))
        text = " ".join(w["text"] for w in d.get("words", [])).strip()
        return {"text": text, "language": language,
                "words": len(d.get("words", [])), "source": final.name}
    if base.exists():
        d = json.loads(base.read_text(encoding="utf-8-sig"))
        segs = d.get("segments") or []
        text = " ".join(s.get("text", "") for s in segs).strip() \
            or " ".join(w["text"] for w in d.get("words", [])).strip()
        return {"text": text, "language": language,
                "words": len(d.get("words", [])), "source": base.name}
    raise FileNotFoundError(
        f"no transcript for job {job!r} - run the rough cut first ({jd})")


# --- ledger lookup -----------------------------------------------------------
def _entry_for_job(job: str) -> tuple[str | None, dict | None]:
    for src_name, entry in state.load().get("processed", {}).items():
        if entry.get("job") == job:
            return src_name, entry
    return None, None


def target_name(job: str) -> str:
    """Description filename: the exported video's stem + .txt, else <job>.txt."""
    _, entry = _entry_for_job(job)
    exported = (entry or {}).get("exported")
    stem = Path(exported).stem if exported else job
    return f"{stem}.txt"


# --- upload ------------------------------------------------------------------
def upload(job: str, txt_name: str, overwrite: bool = False) -> dict:
    src = Path(config.EXPORT_DIR) / txt_name
    if not src.is_file():
        raise FileNotFoundError(f"description not found in export folder: {src}")
    dest_dir = Path(config.UPLOAD_DIR)
    if not dest_dir.is_dir():
        raise FileNotFoundError(
            f"team Drive folder not found (is Google Drive running?): {dest_dir}")
    dest = dest_dir / txt_name

    if dest.exists() and not overwrite and dest.stat().st_size != src.stat().st_size:
        raise FileExistsError(
            f"a different description with this name already exists at the "
            f"destination; re-run with --overwrite to replace: {dest}")

    shutil.copy2(src, dest)
    if dest.stat().st_size != src.stat().st_size:
        raise IOError("description upload size mismatch after copy")

    # Record on the video's ledger entry WITHOUT touching exported/uploaded_at.
    src_name, _ = _entry_for_job(job)
    if src_name:
        state.mark(src_name, description_txt=txt_name,
                   description_uploaded_at=state.now())
    return {"description": txt_name, "dest": str(dest), "link": config.UPLOAD_LINK}


# --- CLI ---------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Course-portal description helper.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_text = sub.add_parser("text", help="print the edited video's transcript")
    p_text.add_argument("job")

    p_name = sub.add_parser("name", help="print the .txt filename + export dir")
    p_name.add_argument("job")

    p_up = sub.add_parser("upload", help="upload a description .txt to Drive")
    p_up.add_argument("job")
    p_up.add_argument("txt", help="description filename inside the export folder")
    p_up.add_argument("--overwrite", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "text":
        info = transcript_text(args.job)
        print(f"[transcript] job={args.job} source={info['source']} "
              f"language={info['language']} words={info['words']}\n")
        print(info["text"])
        return 0

    if args.cmd == "name":
        result = {"name": target_name(args.job), "export_dir": config.EXPORT_DIR}
        print(result["name"])
        print("\nDRIVE_SYNC_JSON")
        print(json.dumps(result, ensure_ascii=False))
        print("END_DRIVE_SYNC_JSON")
        return 0

    if args.cmd == "upload":
        result = upload(args.job, args.txt, overwrite=args.overwrite)
        print(f"Uploaded description -> {result['dest']}")
        print("\nDRIVE_SYNC_JSON")
        print(json.dumps(result, ensure_ascii=False))
        print("END_DRIVE_SYNC_JSON")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
