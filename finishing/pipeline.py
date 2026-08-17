"""CFE orchestrator. Phase 1 (--prep): emit enriched transcript + manifest
skeleton + style frames for Claude. Phase 2 (default): validate the manifest
Claude wrote, then build the polished draft. CapCut must be CLOSED to build."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

from roughcut.mac_compat import stage_media

from . import config
from .timemap import enrich_transcript
from .assets_gen import probe_duration, sample_style_ref
from .beats import load_manifest, validate
from .build_finish import build

ROOT = Path(__file__).resolve().parent.parent


def _job_dir(job: str) -> Path:
    return ROOT / "jobs" / job


def prep(job: str, no_intro: bool = False) -> dict:
    jd = _job_dir(job)
    transcript = json.loads((jd / "transcript.json").read_text(encoding="utf-8"))
    edl = json.loads((jd / "edl.json").read_text(encoding="utf-8"))
    # Compute the intro offset once via ffprobe so transcript_final.json and the
    # build draft use the SAME canonical intro duration — they must never diverge.
    # MUST match the build's intro decision: pass --no-intro to prep too when the
    # build will skip the intro (e.g. middle/last parts of a split), or every
    # caption/card lands intro_dur seconds late.
    intro_dur = 0.0 if no_intro else (
        probe_duration(config.INTRO_PATH) if Path(config.INTRO_PATH).exists() else 0.0)
    enriched = enrich_transcript(transcript, edl, intro_dur=intro_dur)
    (jd / "transcript_final.json").write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    # Manifest skeleton (Claude overwrites finishing_manifest.json).
    (jd / "finishing_manifest.skeleton.json").write_text(
        json.dumps({"job": job, "beats": []}, indent=2), encoding="utf-8")
    frames = sample_style_ref(config.STYLE_REF_DIR, str(jd / "style_frames"))
    print(f"[prep] {len(enriched['words'])} words, final_duration="
          f"{enriched['final_duration']}s, {len(frames)} style frames")
    return {"job_dir": str(jd), "final_duration": enriched["final_duration"],
            "style_frames": frames}


def run_build(job: str, *, accent_hex: str, name_title, do_end_screen: bool,
              drafts_root: str | None = None, intro_zoom: bool = False,
              auto_caption: bool = False, no_intro: bool = False,
              no_outro: bool = False) -> dict:
    jd = _job_dir(job)
    edl = json.loads((jd / "edl.json").read_text(encoding="utf-8"))
    enriched = json.loads((jd / "transcript_final.json").read_text(encoding="utf-8"))
    manifest = load_manifest(str(jd / "finishing_manifest.json"))
    # With auto-captions, the manifest may legitimately hold only card/zoom beats
    # (captions come from the transcript), so an empty beat list is allowed.
    if manifest.get("beats"):
        errs = validate(manifest, enriched["final_duration"])
        if errs:
            raise ValueError("invalid manifest:\n  - " + "\n  - ".join(errs))
    elif not auto_caption:
        raise ValueError("manifest has no beats")

    captions = None
    if auto_caption:
        from .beats import normalize
        from .captions import build_captions
        from .build_finish import _CARD_TREATMENTS
        norm = normalize(manifest)
        card_windows = [(b["final_in"], b["final_out"]) for b in norm["beats"]
                        if b["treatment"] in _CARD_TREATMENTS]
        captions = build_captions(enriched["words"], card_windows)

    root = drafts_root or config.DRAFTS_ROOT
    outro = None if no_outro else (config.OUTRO_PATH if Path(config.OUTRO_PATH).exists() else None)
    intro = None if no_intro else (config.INTRO_PATH if Path(config.INTRO_PATH).exists() else None)
    draft_name = job.replace("_", " ").title() + " (CFE Edit)"
    path = build(edl, manifest, draft_name, drafts_root=root,
                 accent_hex=accent_hex, outro_path=outro, intro_path=intro,
                 do_end_screen=do_end_screen, name_title=name_title,
                 intro_zoom=intro_zoom, captions=captions,
                 assets_dir=str(jd / "cfe_assets"))
    print(f"[build] draft -> {path}  ({len(manifest['beats'])} beats, "
          f"{len(captions or [])} captions)")
    # macOS: CapCut is sandboxed and cannot read media inside OneDrive, so copy
    # anything it references to ~/Movies and repoint the draft (no-op on Windows).
    st = stage_media(path, job)
    if st["staged"] or st["reused"]:
        print(f"[stage] media for CapCut -> {st['root']} "
              f"({len(st['staged'])} copied, {len(st['reused'])} reused)")
    return {"draft_path": path, "n_beats": len(manifest["beats"]),
            "n_captions": len(captions or [])}


def capcut_is_running() -> bool:
    try:
        if sys.platform == "darwin":
            # macOS: pgrep exits 0 if a process named CapCut is running.
            out = subprocess.run(
                ["pgrep", "-x", "CapCut"],
                capture_output=True, text=True, check=False)
            return out.returncode == 0
        out = subprocess.run(
            ["powershell", "-c",
             "[bool](Get-Process CapCut -ErrorAction SilentlyContinue)"],
            capture_output=True, text=True, check=False)
        return out.stdout.strip().lower() == "true"
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="CapCut Finishing Editor pipeline")
    ap.add_argument("job", help="rough-cut job name under jobs/")
    ap.add_argument("--prep", action="store_true",
                    help="emit enriched transcript + manifest skeleton + style frames")
    ap.add_argument("--accent", default=config.ACCENT_HEX)
    ap.add_argument("--name-title", default=None, help='lower-third "Name|Title"')
    ap.add_argument("--no-endscreen", action="store_true")
    ap.add_argument("--intro-zoom", action="store_true",
                    help="add a subtle quick push-in on the company intro clip")
    ap.add_argument("--captions", action="store_true",
                    help="auto-caption the whole video from the transcript "
                         "(continuous subtitles); cards still come from the manifest")
    ap.add_argument("--no-intro", action="store_true",
                    help="skip the company intro (e.g. for middle/last parts of a split)")
    ap.add_argument("--no-outro", action="store_true",
                    help="skip the company outro (e.g. for non-final parts of a split)")
    ap.add_argument("--drafts-root", default=None)
    a = ap.parse_args()
    if a.prep:
        prep(a.job, no_intro=a.no_intro)
        return
    if capcut_is_running():
        raise SystemExit("CapCut is running — close it before building the draft.")
    run_build(a.job, accent_hex=a.accent, name_title=a.name_title,
              do_end_screen=not a.no_endscreen, drafts_root=a.drafts_root,
              intro_zoom=a.intro_zoom, auto_caption=a.captions,
              no_intro=a.no_intro, no_outro=a.no_outro)


if __name__ == "__main__":
    main()
