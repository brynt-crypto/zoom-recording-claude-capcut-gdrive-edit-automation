"""/animate orchestrator.

Phases (run in order, each its own CLI call so Claude can gate between them):
  --transcribe  audio -> jobs/<job>/transcript.json           (reuses whisper)
  --prep        emit storyboard.skeleton.json + author stats   (Claude writes storyboard.json)
  --generate    storyboard.json -> jobs/<job>/scenes/*.png     (spends money unless --dry-run)
  --build       storyboard.json + stills + narration -> CapCut draft (CapCut CLOSED)
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

from . import config, storyboard

ROOT = Path(__file__).resolve().parent.parent


def _job_dir(job: str) -> Path:
    d = ROOT / "jobs" / job
    d.mkdir(parents=True, exist_ok=True)
    return d


def capcut_is_running() -> bool:
    try:
        out = subprocess.run(
            ["powershell", "-c",
             "[bool](Get-Process CapCut -ErrorAction SilentlyContinue)"],
            capture_output=True, text=True, check=False)
        return out.stdout.strip().lower() == "true"
    except Exception:
        return False


def find_references(job: str, explicit: str | None = None) -> list[str]:
    """Locate an optional reference storyboard/brief for Claude to follow.

    Priority: an explicit --reference path; else jobs/<job>/reference.*; else any
    files in assets/storyboard_ref/. Returns absolute paths (may be empty).
    """
    if explicit:
        p = Path(explicit)
        if not p.exists():
            raise SystemExit(f"--reference not found: {explicit}")
        return [str(p.resolve())]
    hits: list[str] = []
    jd = _job_dir(job)
    for f in sorted(jd.glob("reference.*")):
        if f.suffix.lower() in config.REFERENCE_EXTS:
            hits.append(str(f.resolve()))
    ref_dir = Path(config.STORYBOARD_REF_DIR)
    if ref_dir.exists():
        for f in sorted(ref_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in config.REFERENCE_EXTS:
                hits.append(str(f.resolve()))
    return hits


def _narration_dur(job: str) -> float:
    t = json.loads((_job_dir(job) / "transcript.json").read_text(encoding="utf-8"))
    return float(t.get("duration") or 0.0)


def _audio_path(job: str) -> str:
    """The narration source recorded in transcript.json (kept as the soundtrack)."""
    t = json.loads((_job_dir(job) / "transcript.json").read_text(encoding="utf-8"))
    return t["source"]


def do_transcribe(audio: str, job: str, *, model: str, device: str,
                  compute: str, language: str | None) -> None:
    from roughcut.transcribe import transcribe
    out = _job_dir(job) / "transcript.json"
    d = transcribe(audio, str(out), model=model, device=device,
                   compute=compute, language=language)
    print(f"[transcribe] {len(d['words'])} words, {d['duration']:.1f}s, "
          f"lang={d['language']} -> {out}")


def do_prep(job: str, reference: str | None = None) -> None:
    jd = _job_dir(job)
    transcript = json.loads((jd / "transcript.json").read_text(encoding="utf-8"))
    dur = float(transcript.get("duration") or 0.0)
    n_seg = len(transcript.get("segments") or [])
    suggested = max(1, round(dur / config.SCENE_TARGET_SEC))
    skeleton = {
        "job": job,
        "style": "",
        "scenes": [{
            "id": 1, "start": 0.0, "end": round(min(dur, config.SCENE_TARGET_SEC), 2),
            "spoken": "", "caption": "", "image_prompt": "",
            "negative_prompt": "", "motion": "zoom_in", "emphasis": False,
        }],
    }
    (jd / "storyboard.skeleton.json").write_text(
        json.dumps(skeleton, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[prep] narration={dur:.1f}s, {n_seg} transcript segments")
    print(f"[prep] suggest ~{suggested} scenes "
          f"({config.SCENE_MIN_SEC:g}-{config.SCENE_MAX_SEC:g}s each, "
          f"target {config.SCENE_TARGET_SEC:g}s)")
    print(f"[prep] author jobs/{job}/storyboard.json (schema: "
          f"animate/prompts/03_storyboard.md); scenes must be contiguous from 0.0 "
          f"to ~{dur:.1f}s")
    refs = find_references(job, reference)
    if refs:
        print(f"[prep] reference storyboard found — READ before authoring and "
              f"follow it for scene ideas / visual style:")
        for r in refs:
            print(f"         {r}")
    else:
        print(f"[prep] no reference storyboard (optional). To add one: pass "
              f"--reference <path>, or drop a file in jobs/{job}/reference.* or "
              f"{config.STORYBOARD_REF_DIR}")


def _load_valid_storyboard(job: str) -> dict:
    jd = _job_dir(job)
    sb = storyboard.load(jd / "storyboard.json")
    errs = storyboard.validate(sb, _narration_dur(job))
    if errs:
        raise SystemExit("invalid storyboard.json:\n  - " + "\n  - ".join(errs))
    return sb


def do_generate(job: str, *, provider: str, tier: str, dry_run: bool,
                regen: set[int]) -> None:
    from . import providers
    sb = _load_valid_storyboard(job)
    scenes_dir = _job_dir(job) / "scenes"
    res = providers.generate(sb["scenes"], scenes_dir, sb.get("style", ""),
                             provider=provider, tier=tier, dry_run=dry_run,
                             regen_ids=regen)
    tag = "dry-run" if dry_run else f"provider={res['provider']}"
    print(f"[generate] {tag}: generated={len(res['generated'])} "
          f"skipped={len(res['skipped'])} failed={len(res['failed'])} "
          f"cost=${res['cost_usd']:.2f}")
    if res["needs_manual"]:
        print(f"[generate] MANUAL: create {len(res['needs_manual'])} images and save "
              f"them as scene_<id>.png in {scenes_dir}")
        print(f"[generate] prompt sheet -> {res['sheet']}")
        print(f"[generate] then run --build (or --generate again to confirm all exist)")
    for f in res["failed"]:
        print(f"  ! scene {f['id']} FAILED: {f['error']}")
    if res["failed"]:
        raise SystemExit("some scenes failed — edit their prompts and re-run "
                         "--generate --regen <ids>")


def do_build(job: str, *, draft_name: str | None, drafts_root: str | None,
             no_branding: bool) -> None:
    from . import build_draft
    if capcut_is_running():
        raise SystemExit("CapCut is running — close it before building the draft.")
    sb = _load_valid_storyboard(job)
    root = drafts_root or config.DRAFTS_ROOT
    name = draft_name or (" ".join(job.replace("_", " ").split()).title() + " (Animated)")
    intro = None if no_branding else (config.INTRO_PATH if Path(config.INTRO_PATH).exists() else None)
    outro = None if no_branding else (config.OUTRO_PATH if Path(config.OUTRO_PATH).exists() else None)
    res = build_draft.build(
        job, sb["scenes"], _audio_path(job), str(_job_dir(job) / "scenes"),
        name, drafts_root=root, intro_path=intro, outro_path=outro)
    print(f"[build] draft -> {res['draft_path']}")
    print(f"[build] {res['n_scenes']} scenes, {res['n_captions']} captions, "
          f"intro={res['intro_dur']}s  (open CapCut to edit)")


def _parse_ids(s: str | None) -> set[int]:
    if not s:
        return set()
    return {int(x) for x in s.replace(" ", "").split(",") if x}


def main() -> None:
    ap = argparse.ArgumentParser(description="/animate pipeline")
    ap.add_argument("target", help="audio path (with --transcribe) or job name")
    ap.add_argument("--name", default=None, help="job name (defaults to audio filename stem)")
    ap.add_argument("--transcribe", action="store_true")
    ap.add_argument("--prep", action="store_true")
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--build", action="store_true")
    # generation
    ap.add_argument("--provider", default=config.DEFAULT_PROVIDER,
                    choices=["manual", "imagen", "codex"],
                    help="image source (default: manual = you drop in images)")
    ap.add_argument("--dry-run", action="store_true", help="placeholder images, no cost")
    ap.add_argument("--fast", action="store_true", help="Imagen fast tier")
    ap.add_argument("--ultra", action="store_true", help="Imagen ultra tier")
    ap.add_argument("--regen", default=None, help="comma ids to regenerate, e.g. 3,7")
    ap.add_argument("--reference", default=None,
                    help="path to a reference storyboard/brief (.md/.txt/.pdf) for prep")
    # transcription
    ap.add_argument("--model", default=config.WHISPER_MODEL)
    ap.add_argument("--device", default=config.WHISPER_DEVICE)
    ap.add_argument("--compute", default=config.WHISPER_COMPUTE)
    ap.add_argument("--language", default=config.LANGUAGE)
    # build
    ap.add_argument("--draft-name", default=None)
    ap.add_argument("--drafts-root", default=None)
    ap.add_argument("--no-branding", action="store_true")
    a = ap.parse_args()

    tier = "fast" if a.fast else ("ultra" if a.ultra else config.DEFAULT_TIER)

    if a.transcribe:
        job = a.name or Path(a.target).stem.replace(" ", "_")
        do_transcribe(a.target, job, model=a.model, device=a.device,
                      compute=a.compute, language=a.language)
        return
    # For every other phase, `target` is the job name.
    job = a.target
    if a.prep:
        do_prep(job, reference=a.reference)
    elif a.generate:
        do_generate(job, provider=a.provider, tier=tier, dry_run=a.dry_run,
                    regen=_parse_ids(a.regen))
    elif a.build:
        do_build(job, draft_name=a.draft_name, drafts_root=a.drafts_root,
                 no_branding=a.no_branding)
    else:
        ap.error("choose one of --transcribe / --prep / --generate / --build")


if __name__ == "__main__":
    main()
