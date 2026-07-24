from finishing.captions import build_captions


def _w(i, s, e, t):
    return {"i": i, "final_start": s, "final_end": e, "text": t}


def test_splits_on_sentence_end():
    words = [_w(0, 0.0, 0.4, "Hello"), _w(1, 0.4, 0.9, "world."),
             _w(2, 1.0, 1.4, "Next"), _w(3, 1.4, 1.8, "one.")]
    caps = build_captions(words)
    assert [c["text"] for c in caps] == ["Hello world.", "Next one."]
    assert caps[0]["final_in"] == 0.0 and caps[0]["final_out"] == 0.9


def test_splits_on_max_chars():
    words = [_w(i, i * 0.5, i * 0.5 + 0.4, "word") for i in range(20)]
    caps = build_captions(words, max_chars=24)
    assert len(caps) > 1
    assert all(len(c["text"]) <= 24 for c in caps)


def test_splits_on_gap():
    words = [_w(0, 0.0, 0.4, "before"), _w(1, 3.0, 3.4, "after")]
    caps = build_captions(words, max_gap=0.8)
    assert [c["text"] for c in caps] == ["before", "after"]


def test_drops_captions_overlapping_card_windows():
    words = [_w(0, 0.0, 0.4, "keep."), _w(1, 5.0, 5.4, "drop."),
             _w(2, 9.0, 9.4, "keep2.")]
    caps = build_captions(words, card_windows=[(4.5, 6.0)])
    assert [c["text"] for c in caps] == ["keep.", "keep2."]


def test_build_uses_captions_for_subtitle_track(tmp_path):
    """build(captions=[...]) puts the continuous captions on the subtitle track."""
    import json, subprocess
    from pathlib import Path
    from finishing.build_finish import build
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                    "-t", "10", "-pix_fmt", "yuv420p", str(src)], check=True, capture_output=True)
    edl = {"source": str(src), "fps": 30, "width": 640, "height": 360,
           "keep": [{"start": 0.0, "end": 10.0}]}
    caps = [{"text": "auto caption one", "final_in": 1.0, "final_out": 3.0},
            {"text": "auto caption two", "final_in": 3.2, "final_out": 5.0}]
    path = build(edl, {"job": "c", "beats": []}, "c_(CFE Edit)_v1",
                 drafts_root=str(tmp_path / "d"), accent_hex="#22D3EE",
                 do_end_screen=False, captions=caps)
    data = json.loads((Path(path) / "draft_content.json").read_text(encoding="utf-8"))
    blob = " ".join(t.get("content") or "" for t in data["materials"].get("texts", []))
    assert "auto caption one" in blob and "auto caption two" in blob
