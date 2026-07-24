"""storyboard.validate() rules (see animate/storyboard.py)."""
from animate import storyboard


def _scene(sid, start, end, motion="zoom_in", prompt="a leaf", caption=""):
    return {"id": sid, "start": start, "end": end, "motion": motion,
            "image_prompt": prompt, "caption": caption}


def _valid_manifest():
    return {"job": "x", "style": "", "scenes": [
        _scene(1, 0.0, 7.0), _scene(2, 7.0, 14.0, motion="pan_left"),
        _scene(3, 14.0, 20.0, motion="static")]}


def test_valid_passes():
    assert storyboard.validate(_valid_manifest(), 20.0) == []


def test_empty_scenes_fail():
    assert storyboard.validate({"scenes": []}, 20.0)


def test_first_must_start_at_zero():
    m = _valid_manifest()
    m["scenes"][0]["start"] = 1.0
    assert any("start at 0.0" in e for e in storyboard.validate(m, 20.0))


def test_gap_detected():
    m = _valid_manifest()
    m["scenes"][1]["start"] = 8.0  # gap after scene 1 (ended 7.0)
    assert any("contiguous" in e for e in storyboard.validate(m, 20.0))


def test_overlap_detected():
    m = _valid_manifest()
    m["scenes"][1]["start"] = 6.0  # overlaps scene 1
    assert any("contiguous" in e for e in storyboard.validate(m, 20.0))


def test_end_beyond_duration():
    m = _valid_manifest()
    assert any("exceeds narration" in e for e in storyboard.validate(m, 15.0))


def test_unknown_motion():
    m = _valid_manifest()
    m["scenes"][0]["motion"] = "barrel_roll"
    assert any("unknown motion" in e for e in storyboard.validate(m, 20.0))


def test_empty_prompt():
    m = _valid_manifest()
    m["scenes"][0]["image_prompt"] = "   "
    assert any("empty image_prompt" in e for e in storyboard.validate(m, 20.0))


def test_too_short_scene():
    m = _valid_manifest()
    m["scenes"][0]["end"] = 1.0
    m["scenes"][1]["start"] = 1.0
    assert any("too short" in e for e in storyboard.validate(m, 20.0))
