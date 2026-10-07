"""CLI: python -m censor <command> <job>

Commands
  filter <job> [--preview WxH]     write the ffmpeg filter script
  encode <job> [--preview WxH]     encode the censored master (writes the filter first)
  map    <job>                     map the windows onto the rough-cut timeline
  verify <job> [--sheet]           check the encoded master against the plan
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

from common.paths import job_dir, media_path
from . import plan as plan_mod, filters, encode, timeline, verify


def _plan_and_paths(job: str, args):
    jd = job_dir(job)
    p = plan_mod.load(args.plan or jd / "censor_plan.json")
    source = args.source or p.get("source") or media_path(f"to_edit/{job}.mp4")
    out = args.out or p.get("output") or media_path(f"to_edit/{job}_censored.mp4")
    return jd, p, Path(source), Path(out)


def _intro_seconds() -> float:
    from roughcut.config import INTRO_PATH
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(INTRO_PATH)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def cmd_filter(args) -> int:
    jd, p, source, out = _plan_and_paths(args.job, args)
    dest = filters.write_filter(p, args.filter_file or jd / "censor_full.filter",
                                preview=args.preview)
    print(f"wrote {dest} — {plan_mod.counts(p)}, preview={args.preview}")
    return 0


def cmd_encode(args) -> int:
    jd, p, source, out = _plan_and_paths(args.job, args)
    if not source.exists():
        sys.exit(f"source not found: {source}")
    if out.exists() and not args.overwrite:
        sys.exit(f"{out} already exists — pass --overwrite to replace it")
    print(f"[censor] {plan_mod.counts(p)}")
    encode.run(p, source, out, filter_file=args.filter_file or jd / "censor_full.filter",
               preview=args.preview, crf=args.crf, preset=args.preset,
               dry_run=args.dry_run)
    print(f"[censor] wrote {out}")
    print("[censor] now run:  python -m censor verify %s" % args.job)
    return 0


def cmd_map(args) -> int:
    jd, p, source, out = _plan_and_paths(args.job, args)
    edl = json.loads((jd / "edl.json").read_text(encoding="utf-8"))
    intro = 0.0 if args.no_intro else _intro_seconds()
    mapped = timeline.map_plan(p, edl, intro)
    total = timeline.content_duration(edl, intro)
    print(f"intro {intro:.2f}s | rough cut content {timeline.hms(total)} (+ outro)")
    for kind in ("blur", "mute"):
        print(f"\n{kind.upper()}S")
        for row in mapped[kind]:
            a, z = row["source"]
            where = (", ".join(f"{timeline.hms(x)}–{timeline.hms(y)}" for x, y in row["cut"])
                     or "not in the cut")
            print(f"  {row['name'][:62]:62s} src {timeline.hms(a)}–{timeline.hms(z)}  ->  {where}")
    dest = jd / "cut_censor_map.json"
    dest.write_text(json.dumps(mapped, indent=1), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


def cmd_verify(args) -> int:
    jd, p, source, out = _plan_and_paths(args.job, args)
    for path in (source, out):
        if not path.exists():
            sys.exit(f"not found: {path}")
    ok = True

    for r in verify.check_blurs(p, source, out):
        a, z = r["window"]
        verdict = "OK" if r["ok"] else "FAIL " + str(r["fails"][:4])
        print(f"{r['name'][:58]:58s} {a:8.2f}-{z:8.2f} frames {r['frames']:4d} "
              f"orig-edges max {r['orig_edges_max']:6d} "
              f"cens-edges max {r['censored_edges_max']:5d} {verdict}")
        ok &= r["ok"]

    d_src, d_out = verify.duration(source), verify.duration(out)
    print(f"duration orig {d_src:.2f} censored {d_out:.2f}")
    if abs(d_src - d_out) > 0.5:
        print("  ^ durations differ by more than 0.5s — the encode dropped or added time")
        ok = False

    for r in verify.check_mutes(p, out):
        peak = "   n/a " if r["peak_dbfs"] is None else f"{r['peak_dbfs']:7.1f}"
        print(f"mute {r['name'][:60]:60s} peak {peak} dBFS {'OK' if r['ok'] else 'FAIL'}")
        ok &= r["ok"]

    if args.sheet:
        extra = [float(t) for t in (args.sheet_times or "").split(",") if t.strip()]
        sheet = verify.contact_sheet(p, out, jd / "censor_verify_sheet.png",
                                     extra_times=extra)
        print("sheet:", sheet or "skipped (Pillow not installed)")

    print("RESULT:", "ALL OK" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m censor", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("job")
        sp.add_argument("--plan", default=None, help="censor plan (default: <job>/censor_plan.json)")
        sp.add_argument("--source", default=None, help="raw recording (default: from the plan)")
        sp.add_argument("--out", default=None, help="censored master (default: from the plan)")
        sp.add_argument("--filter-file", default=None)
        return sp

    p_filter = common(sub.add_parser("filter", help="write the ffmpeg filter script"))
    p_filter.add_argument("--preview", default=None, metavar="WxH")
    p_filter.set_defaults(func=cmd_filter)

    p_enc = common(sub.add_parser("encode", help="encode the censored master"))
    p_enc.add_argument("--preview", default=None, metavar="WxH",
                       help="low-res, video-only preview render")
    p_enc.add_argument("--crf", type=int, default=18)
    p_enc.add_argument("--preset", default="veryfast")
    p_enc.add_argument("--overwrite", action="store_true")
    p_enc.add_argument("--dry-run", action="store_true", help="print the ffmpeg command only")
    p_enc.set_defaults(func=cmd_encode)

    p_map = common(sub.add_parser("map", help="map windows onto the rough-cut timeline"))
    p_map.add_argument("--no-intro", action="store_true",
                       help="the draft has no intro clip in front of the content")
    p_map.set_defaults(func=cmd_map)

    p_ver = common(sub.add_parser("verify", help="check the master against the plan"))
    p_ver.add_argument("--sheet", action="store_true", help="also write a contact sheet")
    p_ver.add_argument("--sheet-times", default=None,
                       help="extra seconds to sample, comma-separated (e.g. a card sliding in)")
    p_ver.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
