"""Shared helpers: ffprobe metadata, paths, time formatting."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> str:
    """Run a command, return stdout, raise with stderr on failure."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr}")
    return p.stdout


def probe(video: str) -> dict:
    """Return {duration, fps, width, height, has_audio} via ffprobe."""
    out = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(video),
    ])
    data = json.loads(out)
    dur = float(data.get("format", {}).get("duration", 0.0))
    v = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    fps = 30.0
    if v and v.get("r_frame_rate"):
        num, _, den = v["r_frame_rate"].partition("/")
        try:
            fps = float(num) / float(den or 1)
        except (ValueError, ZeroDivisionError):
            fps = 30.0
    return {
        "duration": dur,
        "fps": round(fps, 3),
        "width": int(v["width"]) if v else 0,
        "height": int(v["height"]) if v else 0,
        "has_audio": a is not None,
    }


def parse_ts(s: str | float) -> float:
    """Parse a timestamp into seconds. Accepts 90, '90', '1:30', '1:02:03',
    '1:30.5'."""
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if not s:
        raise ValueError("empty timestamp")
    parts = [float(p) for p in s.split(":")]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"bad timestamp: {s!r}")


def parse_ranges(s: str | None) -> list[list[float]]:
    """Parse 'mm:ss-mm:ss,mm:ss-mm:ss' into [[start,end],...] seconds."""
    if not s:
        return []
    out = []
    for chunk in str(s).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        a, _, b = chunk.partition("-")
        out.append([parse_ts(a), parse_ts(b)])
    return out


def hms(t: float) -> str:
    """Seconds -> H:MM:SS.s for human-readable reports."""
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:04.1f}" if h else f"{m}:{s:04.1f}"


def job_dir(root: str | Path, name: str) -> Path:
    d = Path(root) / "jobs" / name
    d.mkdir(parents=True, exist_ok=True)
    return d
