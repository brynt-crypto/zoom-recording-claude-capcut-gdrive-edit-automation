"""Video -> word-level transcript.json via faster-whisper.

transcript.json schema:
{
  "source": "<abs path>", "duration": float, "language": str,
  "model": str,
  "words":    [{"i": int, "start": float, "end": float, "text": str}],
  "segments": [{"start": float, "end": float, "text": str}]
}
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys
from pathlib import Path

from . import config
from .util import probe, run


def _register_cuda_dlls() -> None:
    """Add the NVIDIA cublas/cudnn pip-wheel DLL dirs to the loader path so
    faster-whisper (ctranslate2) can find cublas64_12.dll / cudnn*.dll on
    Windows without a system-wide CUDA install."""
    if sys.platform != "win32":
        return
    sp = Path(__file__).resolve().parent.parent / ".venv" / "Lib" / "site-packages"
    for d in glob.glob(str(sp / "nvidia" / "*" / "bin")):
        try:
            os.add_dll_directory(d)
        except (OSError, AttributeError):
            pass
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def extract_audio(video: str, out_wav: str) -> None:
    run(["ffmpeg", "-y", "-i", str(video), "-ac", "1", "-ar", "16000",
         "-vn", str(out_wav), "-loglevel", "error"])


def transcribe(video: str, out_json: str, *,
               model: str = config.WHISPER_MODEL,
               device: str = config.WHISPER_DEVICE,
               compute: str = config.WHISPER_COMPUTE,
               language: str | None = config.LANGUAGE,
               work_wav: str | None = None) -> dict:
    # CUDA only exists on the Windows GPU box. On any other OS (e.g. macOS, which
    # has no NVIDIA/CUDA runtime), silently fall back to CPU so a `--device cuda`
    # request never crashes at WhisperModel(...). Slower, but it runs.
    if device == "cuda" and sys.platform != "win32":
        print("[transcribe] CUDA unavailable on this OS — using CPU/int8 instead")
        device, compute = "cpu", "int8"
    if device == "cuda":
        _register_cuda_dlls()
    from faster_whisper import WhisperModel

    video = str(Path(video).resolve())
    meta = probe(video)
    if not meta["has_audio"]:
        raise RuntimeError(f"no audio stream in {video}")

    wav = work_wav or str(Path(out_json).with_suffix(".wav"))
    extract_audio(video, wav)

    wm = WhisperModel(model, device=device, compute_type=compute)
    seg_iter, info = wm.transcribe(
        wav, word_timestamps=True, vad_filter=True, language=language,
    )

    words, segments, i = [], [], 0
    for s in seg_iter:
        segments.append({"start": round(s.start, 3), "end": round(s.end, 3),
                         "text": s.text.strip()})
        for w in (s.words or []):
            words.append({"i": i, "start": round(w.start, 3),
                          "end": round(w.end, 3), "text": w.word.strip()})
            i += 1

    data = {
        "source": video,
        "duration": meta["duration"],
        "fps": meta["fps"],
        "width": meta["width"],
        "height": meta["height"],
        "language": info.language,
        "model": model,
        "words": words,
        "segments": segments,
    }
    Path(out_json).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe video to word-level JSON")
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default="transcript.json")
    ap.add_argument("--model", default=config.WHISPER_MODEL)
    ap.add_argument("--device", default=config.WHISPER_DEVICE)
    ap.add_argument("--compute", default=config.WHISPER_COMPUTE)
    ap.add_argument("--language", default=config.LANGUAGE)
    a = ap.parse_args()
    d = transcribe(a.video, a.out, model=a.model, device=a.device,
                   compute=a.compute, language=a.language)
    print(f"{len(d['words'])} words, {len(d['segments'])} segments, "
          f"lang={d['language']} -> {a.out}")


if __name__ == "__main__":
    main()
