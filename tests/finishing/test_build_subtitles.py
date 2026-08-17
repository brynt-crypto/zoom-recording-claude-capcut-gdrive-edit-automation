# tests/finishing/test_build_subtitles.py
import json
from pathlib import Path
from finishing.build_finish import build

EDL = {"source": None, "fps": 30, "width": 1280, "height": 720,
       "keep": [{"start": 0.0, "end": 5.0}, {"start": 6.0, "end": 10.0}]}

def _edl_with_video(tmp_path):
    # Make a tiny real clip so VideoMaterial can read its duration.
    import subprocess
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-t", "10", "-pix_fmt", "yuv420p", str(src)],
                   check=True, capture_output=True)
    e = dict(EDL); e["source"] = str(src); return e

def test_subtitles_written_to_draft(tmp_path):
    edl = _edl_with_video(tmp_path)
    manifest = {"job": "demo", "beats": [
        {"id": 1, "type": "hook", "treatment": "subtitle_only",
         "final_in": 0.5, "final_out": 3.0, "text": "Hello world",
         "placement": "lower_third", "glass": True, "punch_in": None,
         "subtitle_emphasis": False, "reposition_overlays": False,
         "anim_in": "fade", "anim_out": "fade", "accent": None}]}
    root = str(tmp_path / "drafts")
    path = build(edl, manifest, "demo_(CFE Edit)_v1", drafts_root=root, accent_hex="#22D3EE")

    # pycapcut writes draft_content.json; materials.texts is a list of dicts
    # where each dict's "content" field is a JSON-encoded string containing
    # {"styles": [...], "text": "<the actual text>"}.
    # Searching for "Hello world" as a substring of that JSON string is robust.
    data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
    texts = [m for m in data["materials"]["texts"]]
    assert any("Hello world" in (t.get("content") or "") for t in texts), (
        "Expected subtitle text 'Hello world' not found in draft texts material. "
        f"Found texts: {[t.get('content', '')[:80] for t in texts]}"
    )
