# tests/finishing/test_build_endscreen.py
import json, subprocess
from pathlib import Path
from finishing.build_finish import build, versioned_name


def _edl(tmp_path):
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-t", "12", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    return {"source": str(src), "fps": 30, "width": 1280, "height": 720,
            "keep": [{"start": 0.0, "end": 12.0}]}


def test_endscreen_adds_masked_segment_and_versions(tmp_path):
    edl = _edl(tmp_path)
    manifest = {"job": "demo", "beats": [
        {"id": 1, "type": "cta", "treatment": "end_screen", "final_in": 11.0,
         "final_out": 12.0, "text": "Subscribe for more", "placement": "center",
         "glass": True, "punch_in": None, "anim_in": "fade", "anim_out": "fade",
         "subtitle_emphasis": False, "reposition_overlays": False, "accent": None}]}
    root = str(tmp_path / "drafts")
    p1 = build(edl, manifest, "demo (CFE Edit)", drafts_root=root,
               accent_hex="#22D3EE", name_title="Speaker|Founder")
    data = json.loads((Path(p1) / "draft_content.json").read_text(encoding="utf-8"))
    # A video segment carries a mask (the rounded speaker frame).
    masks = data["materials"].get("masks", [])
    assert masks, "expected a rounded rectangle mask for the end-screen crop"
    # End-screen uses a FREEZE FRAME (end_freeze.png), not a replay of the tail
    # video — so the closing seconds are not repeated.
    names = [m.get("material_name", "") for m in data["materials"].get("videos", [])]
    assert any("end_freeze" in n for n in names), (
        f"expected a freeze-frame material for the end-screen, got {names}"
    )
    # Re-build appends " v2" (folder already exists).
    assert versioned_name(root, "demo (CFE Edit)") == "demo (CFE Edit) v2"
