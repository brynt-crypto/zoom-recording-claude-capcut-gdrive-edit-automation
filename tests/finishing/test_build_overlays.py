# tests/finishing/test_build_overlays.py
import json, subprocess
from pathlib import Path
from finishing.build_finish import build

def _edl(tmp_path):
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-t", "10", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    return {"source": str(src), "fps": 30, "width": 1280, "height": 720,
            "keep": [{"start": 0.0, "end": 10.0}]}

def _edl_two_ranges(tmp_path):
    """Two-range EDL: keep [0,5] and [6,10] on a 10s source.

    On the final timeline these map to [0,5] and [5,9] (gap removed).
    A beat straddling the cut boundary 5.0 has its midpoint in one segment.
    """
    src = tmp_path / "clip2.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
                    "-t", "10", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    return {"source": str(src), "fps": 30, "width": 1280, "height": 720,
            "keep": [{"start": 0.0, "end": 5.0}, {"start": 6.0, "end": 10.0}]}

def test_overlay_card_and_punchin(tmp_path):
    edl = _edl(tmp_path)
    manifest = {"job": "demo", "beats": [
        {"id": 1, "type": "tool", "treatment": "right_card", "final_in": 1.0,
         "final_out": 4.0, "text": "LangChain", "placement": "right_card",
         "glass": True, "punch_in": None, "anim_in": "fade", "anim_out": "fade",
         "subtitle_emphasis": False, "reposition_overlays": False, "accent": None},
        {"id": 2, "type": "benefit", "treatment": "subtitle+punch_in", "final_in": 5.0,
         "final_out": 7.0, "text": "Save hours", "placement": "lower_third",
         "glass": True, "punch_in": 1.12, "anim_in": "fade", "anim_out": "fade",
         "subtitle_emphasis": True, "reposition_overlays": False, "accent": None}]}
    root = str(tmp_path / "drafts")
    path = build(edl, manifest, "demo_(CFE Edit)_v1", drafts_root=root,
                 accent_hex="#22D3EE", do_end_screen=False)
    data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
    # An overlay image material exists (the rendered PNG), and base has keyframes.
    assert len(data["materials"].get("videos", [])) >= 2  # base clip + 1 overlay png
    base_track = next(t for t in data["tracks"] if t.get("name") == "base")
    # Base track segment count equals number of keep ranges
    assert len(base_track["segments"]) == len(edl["keep"])
    seg = base_track["segments"][0]
    assert seg["common_keyframes"], "expected punch-in keyframes on base segment"
    # Quick-zoom shape: 4 keyframes (in -> hold -> hold -> out), not a 3-pt pulse.
    total_kf = sum(len(k.get("keyframe_list", [])) for k in seg["common_keyframes"])
    assert total_kf == 4, f"expected 4 quick-zoom keyframes (in/hold/hold/out), got {total_kf}"
    # A card beat must NOT also produce a lower-third subtitle (the card carries
    # the text); the subtitle beat must. Subtitle text is a JSON blob in content.
    sub_blob = " ".join(t.get("content") or "" for t in data["materials"].get("texts", []))
    assert "Save hours" in sub_blob, "subtitle beat should produce a caption"
    assert "LangChain" not in sub_blob, "card beat must not duplicate text as a subtitle"


def test_pseudo_split_keyframes(tmp_path):
    """Pseudo_split produces correct 4-keyframe ramp with clamped ramp on short beats.

    For the SHORT beat (0.5s window, fi=7.0, fo=7.5):
      ramp = min(0.4, (hi-lo)/2) = min(0.4, 0.25) = 0.25
      expected offsets: [lo, lo+ramp, hi-ramp, hi] = [7.0, 7.25, 7.25, 7.5]
      (lo+ramp == hi-ramp is valid — clamp prevents crossing but they may touch)

    Genuine checks (not just sorted):
      - exactly 4 keyframes per animated property
      - offsets are non-decreasing (lo <= lo+ramp <= hi-ramp <= hi)
      - the two middle offsets lie strictly between first and last
        (i.e. the ramp clamp produced offsets[0] < offsets[1] and offsets[2] < offsets[3])
      - the four offsets span the correct beat window in microseconds
    """
    edl = _edl(tmp_path)
    manifest = {"job": "kp_test", "beats": [
        # Normal beat (4s window, well over 0.8s — ramp=0.4 fits without clamping)
        {"id": 10, "type": "kp", "treatment": "pseudo_split", "final_in": 2.0,
         "final_out": 6.0, "text": "Normal beat", "placement": "pseudo_card",
         "glass": True, "punch_in": None, "anim_in": "fade", "anim_out": "fade",
         "subtitle_emphasis": False, "reposition_overlays": False, "accent": None},
        # Short beat (0.5s window, under 0.8s — ramp must be clamped to 0.25)
        {"id": 11, "type": "kp", "treatment": "pseudo_split", "final_in": 7.0,
         "final_out": 7.5, "text": "Short beat", "placement": "pseudo_card",
         "glass": True, "punch_in": None, "anim_in": "fade", "anim_out": "fade",
         "subtitle_emphasis": False, "reposition_overlays": False, "accent": None},
    ]}
    root = str(tmp_path / "drafts2")
    path = build(edl, manifest, "kp_test_(CFE Edit)_v1", drafts_root=root, accent_hex="#22D3EE")
    data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
    base_track = next(t for t in data["tracks"] if t.get("name") == "base")
    seg = base_track["segments"][0]

    # (a) common_keyframes exist — pseudo-split keyframes were applied
    assert seg["common_keyframes"], "expected pseudo-split keyframes on base segment"

    # (b) Genuine ramp-clamp check on the SHORT beat's keyframes.
    # Both beats land on the single base segment. The combined keyframe list has
    # 8 entries per property (4 for each beat). We check the last 4 (short beat).
    # time_offset is in microseconds.
    for kfl in seg["common_keyframes"]:
        offsets = [kf["time_offset"] for kf in kfl["keyframe_list"]]

        # All offsets must be non-decreasing.
        assert offsets == sorted(offsets), (
            f"property {kfl['property_type']} has out-of-order keyframe times: {offsets}"
        )

        # Isolate the 4 keyframes for the SHORT beat (fi=7.0, fo=7.5).
        # Their offsets must all lie in [7_000_000, 7_500_000] µs.
        short_offsets = [o for o in offsets if 7_000_000 <= o <= 7_500_000]
        assert len(short_offsets) == 4, (
            f"expected 4 keyframes in short-beat window for {kfl['property_type']}, "
            f"got {len(short_offsets)}: {short_offsets}"
        )

        o0, o1, o2, o3 = short_offsets
        # First and last span the full beat window.
        assert o0 == 7_000_000, f"first short-beat keyframe should be lo=7.0s, got {o0}"
        assert o3 == 7_500_000, f"last short-beat keyframe should be hi=7.5s, got {o3}"
        # Middle offsets lie strictly inside [lo, hi] — ramp did not cross.
        assert o0 < o1, f"lo+ramp must be > lo (got {o0}, {o1})"
        assert o2 < o3, f"hi-ramp must be < hi (got {o2}, {o3})"
        # Ramp clamp invariant: lo+ramp <= hi-ramp (may be equal for tiny windows).
        assert o1 <= o2, (
            f"ramp clamp violated: lo+ramp ({o1}) > hi-ramp ({o2}) for "
            f"property {kfl['property_type']}"
        )


def test_cross_cut_boundary_beat(tmp_path):
    """FIX 2: A subtitle+punch_in beat whose window straddles a hard cut must succeed.

    EDL: keep [0,5] and [6,10] → final segments [0,5) and [5,9).
    Beat window: final_in=4.5, final_out=5.5 — straddles the cut at 5.0.
    Beat midpoint = 5.0 → falls on the boundary of seg 0 (final_end=5.0).
    _overlapping_segment uses <=, so midpoint 5.0 is matched by seg 0.
    Keyframes are applied to exactly one segment; no crash; build succeeds.
    """
    edl = _edl_two_ranges(tmp_path)
    manifest = {"job": "xcut_test", "beats": [
        {"id": 20, "type": "cta", "treatment": "subtitle+punch_in",
         "final_in": 4.5, "final_out": 5.5, "text": "Cross-cut beat",
         "placement": "lower_third", "glass": True, "punch_in": 1.1,
         "anim_in": "fade", "anim_out": "fade",
         "subtitle_emphasis": False, "reposition_overlays": False, "accent": None},
    ]}
    root = str(tmp_path / "drafts_xcut")
    path = build(edl, manifest, "xcut_(CFE Edit)_v1", drafts_root=root,
                 accent_hex="#22D3EE", do_end_screen=False)
    data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
    base_track = next(t for t in data["tracks"] if t.get("name") == "base")

    # Two keep-range segments on the base track (no intro).
    assert len(base_track["segments"]) == 2, (
        f"expected 2 base segments for two keep ranges, got {len(base_track['segments'])}")

    # Punch-in keyframes applied to exactly one segment (the one containing the midpoint).
    segs_with_kf = [s for s in base_track["segments"] if s.get("common_keyframes")]
    assert len(segs_with_kf) == 1, (
        f"expected keyframes on exactly 1 base segment (midpoint rule), "
        f"got {len(segs_with_kf)}"
    )
