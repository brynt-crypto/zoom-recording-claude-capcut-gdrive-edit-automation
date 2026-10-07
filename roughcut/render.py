"""Render the keep-ranges from an EDL into a single preview MP4 (ffmpeg).

Uses the trim/concat filter graph so cuts are frame-accurate. This is for
sanity-checking the cut decisions before building the editable CapCut draft.
For very long videos with thousands of keep-ranges the filter graph gets large;
render is optional and can be skipped in long-form mode.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

from . import config


def render(edl: dict, out_mp4: str, *, crf: int = config.PREVIEW_CRF,
           preset: str = config.PREVIEW_PRESET) -> None:
    src = edl["source"]
    keep = edl["keep"]
    if not keep:
        raise RuntimeError("EDL has no keep ranges")

    parts, concat_inputs = [], ""
    for i, r in enumerate(keep):
        s, e = r["start"], r["end"]
        parts.append(
            f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}];"
            f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}];"
        )
        # concat expects inputs interleaved per segment: [v0][a0][v1][a1]...
        concat_inputs += f"[v{i}][a{i}]"
    n = len(keep)
    graph = "".join(parts) + f"{concat_inputs}concat=n={n}:v=1:a=1[v][a]"

    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
        "-c:a", "aac", str(out_mp4), "-loglevel", "error",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        # Filter graph too large for argv? fall back to a script file.
        graph_file = Path(out_mp4).with_suffix(".filtergraph.txt")
        graph_file.write_text(graph, encoding="utf-8")
        cmd2 = [
            "ffmpeg", "-y", "-i", str(src),
            "-filter_complex_script", str(graph_file), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-c:a", "aac", str(out_mp4), "-loglevel", "error",
        ]
        p2 = subprocess.run(cmd2, capture_output=True, text=True)
        if p2.returncode != 0:
            raise RuntimeError(f"ffmpeg render failed:\n{p.stderr}\n---\n{p2.stderr}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Render preview MP4 from EDL")
    ap.add_argument("edl")
    ap.add_argument("-o", "--out", default="preview.mp4")
    a = ap.parse_args()
    edl = json.loads(Path(a.edl).read_text(encoding="utf-8"))
    render(edl, a.out)
    print(f"rendered {len(edl['keep'])} segments -> {a.out}")


if __name__ == "__main__":
    main()
