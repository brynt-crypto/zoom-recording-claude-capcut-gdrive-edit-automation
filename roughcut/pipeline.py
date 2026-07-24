"""End-to-end: video -> transcript -> EDL + report -> (optional) preview MP4.

Writes all artifacts into jobs/<name>/. The /roughcut command runs the
transcribe step, lets Claude add semantic cuts, then re-runs decide + render
+ build_draft. Run standalone for the deterministic baseline.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from . import config
from .blackframes import detect as detect_black_ranges, total as black_total
from .mac_compat import stage_media
from .transcribe import transcribe
from .decide import build_edl, write_report
from .render import render

ROOT = Path(__file__).resolve().parent.parent


def run_job(video: str, name: str | None = None, *,
            model: str = config.WHISPER_MODEL,
            device: str = config.WHISPER_DEVICE,
            compute: str = config.WHISPER_COMPUTE,
            language: str | None = config.LANGUAGE,
            min_cut: float = config.MIN_CUT,
            sentence_pause: float = config.SENTENCE_PAUSE,
            clip_start: float = 0.0,
            clip_end: float | None = None,
            exclude_ranges=None,
            detect_black: bool = True,
            extra_cut_indices=None,
            do_render: bool = True,
            do_build: bool = False,
            draft_name: str | None = None,
            drafts_root: str | None = None,
            overwrite: bool = False,
            intro: str | None = config.INTRO_PATH,
            outro: str | None = config.OUTRO_PATH,
            reuse_transcript: bool = True) -> dict:
    video = str(Path(video).resolve())
    name = name or Path(video).stem.replace(" ", "_")
    jd = ROOT / "jobs" / name
    jd.mkdir(parents=True, exist_ok=True)

    tpath = jd / "transcript.json"
    if reuse_transcript and tpath.exists():
        transcript = json.loads(tpath.read_text(encoding="utf-8"))
        print(f"[transcribe] reusing {tpath}")
    else:
        print(f"[transcribe] {Path(video).name} (model={model}, device={device})")
        transcript = transcribe(video, str(tpath), model=model, device=device,
                                compute=compute, language=language,
                                work_wav=str(jd / "audio.wav"))
    print(f"[transcribe] {len(transcript['words'])} words, lang={transcript['language']}")

    # Semantic cuts: Claude writes jobs/<name>/semantic_cuts.json
    # ({"cut_word_indices": [...]}) for false starts / repeated takes.
    if extra_cut_indices is None:
        sc = jd / "semantic_cuts.json"
        if sc.exists():
            extra_cut_indices = json.loads(sc.read_text(encoding="utf-8")).get("cut_word_indices")
            print(f"[decide] applying {len(extra_cut_indices or [])} semantic cuts from {sc.name}")

    # Dead picture: the cut decision is transcript-driven, so a blackout with
    # talking over it would otherwise survive. Fold detected black ranges into
    # the same exclude machinery as a manual --exclude.
    if detect_black:
        black = detect_black_ranges(video)
        if black:
            print(f"[black] {len(black)} black range(s), "
                  f"{black_total(black)}s of dead picture -> excluded")
            for s, e in black[:5]:
                print(f"        {s:9.2f} - {e:9.2f}  ({e - s:.2f}s)")
            if len(black) > 5:
                print(f"        ... and {len(black) - 5} more")
            exclude_ranges = list(exclude_ranges or []) + black
        else:
            print("[black] no black ranges found")

    edl = build_edl(transcript, min_cut=min_cut, sentence_pause=sentence_pause,
                    clip_start=clip_start, clip_end=clip_end,
                    exclude_ranges=exclude_ranges,
                    extra_cut_indices=extra_cut_indices)
    (jd / "edl.json").write_text(json.dumps(edl, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    write_report(edl, transcript, str(jd / "cuts_report.md"))
    s = edl["stats"]
    print(f"[decide] kept {s['kept_sec']}s / {s['original_sec']}s "
          f"({s['removed_pct']}% removed), {s['segments']} segments")

    if do_render:
        out = jd / "preview.mp4"
        print(f"[render] {len(edl['keep'])} segments -> {out}")
        render(edl, str(out))

    draft_path = None
    if do_build:
        from .build_draft import build, DEFAULT_DRAFTS_ROOT
        dn = draft_name or f"{name}_roughcut"
        root = drafts_root or DEFAULT_DRAFTS_ROOT
        intro_p = intro if intro and Path(intro).exists() else None
        outro_p = outro if outro and Path(outro).exists() else None
        print(f"[build] CapCut draft '{dn}' -> {root}"
              + (f"  (+intro {Path(intro_p).name})" if intro_p else " (no intro found)")
              + (f"  (+outro {Path(outro_p).name})" if outro_p else " (no outro found)"))
        draft_path = build(edl, dn, drafts_root=root, allow_replace=overwrite,
                           versioned=not overwrite,
                           intro_path=intro_p, outro_path=outro_p)
        print(f"[build] draft written -> {draft_path}")
        # macOS: CapCut is sandboxed and cannot read media inside OneDrive, so
        # copy anything it references to ~/Movies and repoint the draft (no-op
        # on Windows).
        st = stage_media(draft_path, name)
        if st["staged"] or st["reused"]:
            print(f"[stage] media for CapCut -> {st['root']} "
                  f"({len(st['staged'])} copied, {len(st['reused'])} reused)")

    print(f"[done] artifacts in {jd}")
    return {"job_dir": str(jd), "edl": edl, "draft_path": draft_path}


def main() -> None:
    ap = argparse.ArgumentParser(description="Rough-cut pipeline")
    ap.add_argument("video")
    ap.add_argument("--name", default=None)
    ap.add_argument("--model", default=config.WHISPER_MODEL)
    ap.add_argument("--device", default=config.WHISPER_DEVICE)
    ap.add_argument("--compute", default=config.WHISPER_COMPUTE)
    ap.add_argument("--language", default=config.LANGUAGE)
    ap.add_argument("--min-cut", type=float, default=config.MIN_CUT)
    ap.add_argument("--sentence-pause", type=float, default=config.SENTENCE_PAUSE)
    ap.add_argument("--clip-start", default=None, help="trim everything before this timestamp (mm:ss)")
    ap.add_argument("--clip-end", default=None, help="trim everything after this timestamp (mm:ss)")
    ap.add_argument("--exclude", default=None, help="remove ranges, e.g. '12:30-15:00,40:00-41:10'")
    ap.add_argument("--no-black-detect", action="store_true",
                    help="keep black/dead-picture stretches (they are removed by default)")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--build", action="store_true", help="also write a CapCut draft (CLOSE CapCut first)")
    ap.add_argument("--draft-name", default=None)
    ap.add_argument("--drafts-root", default=None)
    ap.add_argument("--overwrite", action="store_true",
                    help="overwrite the same draft instead of auto-versioning (_v2,...)")
    ap.add_argument("--intro", default=config.INTRO_PATH)
    ap.add_argument("--outro", default=config.OUTRO_PATH)
    ap.add_argument("--no-branding", action="store_true", help="skip intro/outro")
    ap.add_argument("--fresh", action="store_true", help="ignore cached transcript")
    a = ap.parse_args()
    from .util import parse_ts, parse_ranges
    run_job(a.video, a.name, model=a.model, device=a.device, compute=a.compute,
            language=a.language, min_cut=a.min_cut, sentence_pause=a.sentence_pause,
            clip_start=parse_ts(a.clip_start) if a.clip_start else 0.0,
            clip_end=parse_ts(a.clip_end) if a.clip_end else None,
            exclude_ranges=parse_ranges(a.exclude),
            detect_black=not a.no_black_detect,
            do_render=not a.no_render, do_build=a.build,
            draft_name=a.draft_name, drafts_root=a.drafts_root,
            overwrite=a.overwrite,
            intro=None if a.no_branding else a.intro,
            outro=None if a.no_branding else a.outro,
            reuse_transcript=not a.fresh)


if __name__ == "__main__":
    main()
