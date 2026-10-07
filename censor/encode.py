"""Encode the censored master from a plan's filter script."""
from __future__ import annotations
import subprocess
from pathlib import Path

from . import filters


def encode_cmd(source, out_path, filter_file, *, audio_leg: bool,
               crf: int = 18, preset: str = "veryfast", ffmpeg: str = "ffmpeg") -> list[str]:
    cmd = [ffmpeg, "-y", "-i", str(source),
           "-filter_complex_script", str(filter_file), "-map", "[vout]"]
    # Only map [aout] when the filter actually defines it; otherwise the input's
    # audio is copied through untouched.
    cmd += ["-map", "[aout]"] if audio_leg else ["-map", "0:a?"]
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd += ["-c:a", "aac", "-b:a", "192k"] if audio_leg else ["-c:a", "copy"]
    cmd += [str(out_path)]
    return cmd


def run(plan: dict, source, out_path, *, filter_file=None, preview: str | None = None,
        crf: int = 18, preset: str = "veryfast", ffmpeg: str = "ffmpeg",
        dry_run: bool = False) -> Path:
    """Write the filter script, then encode. Returns the output path."""
    out_path = Path(out_path)
    filter_file = Path(filter_file or out_path.with_suffix(".filter"))
    filters.write_filter(plan, filter_file, preview=preview)
    cmd = encode_cmd(source, out_path, filter_file,
                     audio_leg=filters.has_audio_leg(plan, preview=preview),
                     crf=crf, preset=preset, ffmpeg=ffmpeg)
    print("[censor] " + " ".join(cmd))
    if not dry_run:
        subprocess.run(cmd, check=True)
    return out_path
