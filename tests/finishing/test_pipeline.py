import json, subprocess
from pathlib import Path
import finishing.pipeline as pipe


def _job(tmp_path, monkeypatch):
    root = tmp_path / "jobs" / "demo"; root.mkdir(parents=True)
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                    "-t", "8", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    (root / "edl.json").write_text(json.dumps({
        "source": str(src), "fps": 30, "width": 640, "height": 360,
        "keep": [{"start": 0.0, "end": 8.0}]}), encoding="utf-8")
    (root / "transcript.json").write_text(json.dumps({
        "source": str(src), "fps": 30.0, "width": 640, "height": 360,
        "words": [{"i": 0, "start": 1.0, "end": 1.5, "text": "hi"}]}), encoding="utf-8")
    monkeypatch.setattr(pipe, "ROOT", tmp_path)
    return root


def test_prep_writes_enriched_transcript(tmp_path, monkeypatch):
    root = _job(tmp_path, monkeypatch)
    # Monkeypatch INTRO_PATH to a nonexistent path so intro_dur=0.0 and the
    # expected final_duration (8.0 = total keep-range length) is deterministic.
    monkeypatch.setattr(pipe.config, "INTRO_PATH", str(tmp_path / "no_intro.mp4"))
    out = pipe.prep("demo")
    tf = json.loads((root / "transcript_final.json").read_text(encoding="utf-8"))
    assert tf["final_duration"] == 8.0
    assert out["final_duration"] == 8.0


def test_run_build_rejects_invalid_manifest(tmp_path, monkeypatch):
    root = _job(tmp_path, monkeypatch)
    monkeypatch.setattr(pipe.config, "INTRO_PATH", str(tmp_path / "no_intro.mp4"))
    pipe.prep("demo")
    (root / "finishing_manifest.json").write_text(json.dumps({
        "job": "demo", "beats": [{"id": 1, "type": "hook", "treatment": "BAD",
                                  "final_in": 0.0, "final_out": 2.0, "text": "x"}]}),
        encoding="utf-8")
    try:
        pipe.run_build("demo", accent_hex="#22D3EE", name_title=None,
                       do_end_screen=False, drafts_root=str(tmp_path / "drafts"))
        assert False, "should have raised"
    except ValueError as e:
        assert "treatment" in str(e)
