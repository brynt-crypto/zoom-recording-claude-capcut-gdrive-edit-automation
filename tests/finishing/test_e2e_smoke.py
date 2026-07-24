# tests/finishing/test_e2e_smoke.py
import json, subprocess
from pathlib import Path
import finishing.pipeline as pipe


def test_full_chain(tmp_path, monkeypatch):
    jd = tmp_path / "jobs" / "smoke"; jd.mkdir(parents=True)
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                    "-t", "10", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    (jd / "edl.json").write_text(json.dumps({"source": str(src), "fps": 30,
        "width": 640, "height": 360, "keep": [{"start": 0.0, "end": 10.0}]}), encoding="utf-8")
    (jd / "transcript.json").write_text(json.dumps({"source": str(src), "fps": 30.0,
        "width": 640, "height": 360,
        "words": [{"i": 0, "start": 1.0, "end": 1.5, "text": "hi"}]}), encoding="utf-8")
    monkeypatch.setattr(pipe, "ROOT", tmp_path)
    # Patch INTRO_PATH to a nonexistent path so intro_dur=0.0 and beat times in
    # the hard-coded manifest (final_in=1.0 / 5.0) remain valid against final_duration=10.0.
    monkeypatch.setattr(pipe.config, "INTRO_PATH", str(tmp_path / "no_intro.mp4"))
    pipe.prep("smoke")
    (jd / "finishing_manifest.json").write_text(json.dumps({"job": "smoke", "beats": [
        {"id": 1, "type": "hook", "treatment": "right_card", "final_in": 1.0,
         "final_out": 4.0, "text": "AI Skills", "placement": "right_card"},
        {"id": 2, "type": "cta", "treatment": "subtitle+punch_in", "final_in": 5.0,
         "final_out": 7.0, "text": "Subscribe", "punch_in": 1.1, "placement": "lower_third"}]}),
        encoding="utf-8")
    res = pipe.run_build("smoke", accent_hex="#22D3EE", name_title="Phil|Founder",
                         do_end_screen=True, drafts_root=str(tmp_path / "drafts"))
    assert Path(res["draft_path"]).exists()
    data = json.loads((Path(res["draft_path"]) / "draft_content.json").read_text(encoding="utf-8"))
    assert any(t.get("name") == "base" for t in data["tracks"])
    assert any(t.get("name") == "overlay" for t in data["tracks"])
    assert any(t.get("name") == "subtitles" for t in data["tracks"])
